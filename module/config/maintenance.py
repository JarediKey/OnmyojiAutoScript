"""Cross-process leases: deployment may stop workers only inside scheduler waits."""
from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import time
from datetime import datetime, timezone, timedelta

from filelock import FileLock, Timeout


class DeploymentBusy(RuntimeError):
    pass


def account_key(name):
    return hashlib.sha256(name.encode('utf-8')).hexdigest()[:24]


def config_digest(root, name):
    return hashlib.sha256((root / 'config' / (name + '.json')).read_bytes()).hexdigest()


def state_dir(root):
    result = root / 'log' / 'maintenance'
    result.mkdir(parents=True, exist_ok=True)
    return result


class WorkerLease:
    def __init__(self, root, name):
        self.root = Path(root)
        self.name = name
        folder = state_dir(self.root)
        key = account_key(name)
        self.lock = FileLock(str(folder / (key + '.lock')))
        self.state_path = folder / (key + '.json')
        self.admission = FileLock(str(folder / 'admission.lock'))

    def write(self, state, wake=0):
        data = {'version': 1, 'name': self.name, 'pid': os.getpid(),
                'state': state, 'wake': wake, 'config': config_digest(self.root, self.name)}
        temp = self.state_path.with_suffix('.tmp')
        temp.write_text(json.dumps(data), encoding='utf-8')
        os.replace(temp, self.state_path)

    @contextmanager
    def active(self):
        # Wait outside global admission so a recovery hold on one profile does
        # not block unrelated workers. Deployment takes all locks nonblocking.
        self.lock.acquire()
        try:
            with self.admission:
                self.write('active')
            yield self
        finally:
            self.state_path.unlink(missing_ok=True)
            self.lock.release()

    @contextmanager
    def idle(self, future):
        wake = time.time() + (future - datetime.now()).total_seconds()
        self.write('idle', wake)
        self.lock.release()
        try:
            yield
        finally:
            self.lock.acquire()
            self.write('active')


def maintenance_worker(func):
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        with WorkerLease(Path.cwd(), self.config_name).active() as lease:
            self._maintenance_lease = lease
            return func(self, *args, **kwargs)
    return wrapped


def maintenance_idle(func):
    @wraps(func)
    def wrapped(self, future):
        lease = getattr(self, '_maintenance_lease', None)
        if lease is None:
            return func(self, future)
        with lease.idle(future):
            return func(self, future)
    return wrapped


@contextmanager
def acquire_idle_workers(root, workers, minimum_seconds=180):
    """Fail immediately if any worker is busy, stale, or due to wake soon.

    `workers` is the backend's live name-to-PID map, not the UI's RUNNING flags.
    Leases remain held across the short stop/switch/start-backend operation.
    """
    root = Path(root)
    folder = state_dir(root)
    locks = []
    try:
        admission = FileLock(str(folder / 'admission.lock'))
        admission.acquire(timeout=0)
        locks.append(admission)
        names = {p.stem for p in (root / 'config').glob('*.json') if p.stem != 'template'}
        if not set(workers) <= names:
            raise DeploymentBusy('Worker/configuration list changed')
        for name in sorted(names):
            lock = FileLock(str(folder / (account_key(name) + '.lock')))
            lock.acquire(timeout=0)
            locks.append(lock)
            if name not in workers:
                continue
            path = folder / (account_key(name) + '.json')
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                raise DeploymentBusy('A live worker has no trustworthy idle acknowledgment') from exc
            if (data.get('version') != 1 or data.get('pid') != workers[name]
                    or data.get('name') != name or data.get('state') != 'idle'
                    or data.get('wake', 0) < time.time() + minimum_seconds
                    or data.get('config') != config_digest(root, name)):
                raise DeploymentBusy('A live worker is active, due soon, or has changed configuration')
        # Check current scheduler data too, not just the worker's cached wake.
        now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
        for name in workers:
            config = json.loads((root / 'config' / (name + '.json')).read_text(encoding='utf-8-sig'))
            for task in config.values():
                if not isinstance(task, dict):
                    continue
                scheduler = task.get('scheduler')
                if not isinstance(scheduler, dict) or not scheduler.get('enable'):
                    continue
                due = datetime.fromisoformat(scheduler['next_run'])
                if (due - now).total_seconds() < minimum_seconds:
                    raise DeploymentBusy('A configured task is pending or due soon')
        yield
    except Timeout as exc:
        raise DeploymentBusy('A worker is executing outside its idle wait') from exc
    finally:
        for lock in reversed(locks):
            lock.release()
