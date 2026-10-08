"""Loopback notification receiver and bounded recovery coordinator.

Run in the interactive Windows session, independently of SSH and the OAS backend.
Only terminal notifications (or explicit operator seeds) create incidents.
"""
import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import secrets
import shutil
import sqlite3
import sys
import threading
import time

from filelock import FileLock, Timeout
from policy import enabled_tasks, plan_recovery, terminal_profile
from runtime import Runtime

LOG = logging.getLogger('recovery')


class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, name TEXT, '
                       'created REAL, state TEXT, detail TEXT, updated REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS terminal_events (incident TEXT, received REAL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def add(self, name, payload):
        now = time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT id FROM incidents WHERE name=? AND state NOT IN ('recovered','manual')",
                             (name,)).fetchone()
            if row:
                db.execute('INSERT INTO terminal_events VALUES (?,?)', (row[0], now))
                return row[0]
            recent = db.execute('SELECT created FROM incidents WHERE name=? ORDER BY created DESC LIMIT 1',
                                (name,)).fetchone()
            state = 'needs_ai' if recent and now - recent[0] < 3600 else 'queued'
            key = secrets.token_hex(12)
            db.execute('INSERT INTO terminal_events VALUES (?,?)', (key, now))
            db.execute('INSERT INTO incidents VALUES(?,?,?,?,?,?)',
                       (key, name, now, state, json.dumps(payload, ensure_ascii=False), now))
            return key

    def notified_since(self, key, since):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM terminal_events WHERE incident=? AND received>? LIMIT 1',
                              (key, since)).fetchone() is not None

    def update(self, key, state, detail):
        with self.connect() as db:
            db.execute('UPDATE incidents SET state=?,detail=?,updated=? WHERE id=?',
                       (state, json.dumps(detail, ensure_ascii=False), time.time(), key))

    def rows(self, states=None):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            sql = 'SELECT * FROM incidents'
            args = []
            if states:
                sql += ' WHERE state IN (' + ','.join('?' for _ in states) + ')'
                args = list(states)
            return [dict(r) for r in db.execute(sql + ' ORDER BY created', args)]


class Coordinator:
    def __init__(self, settings):
        self.settings = settings
        self.runtime = Runtime(settings)
        self.store = Store(str(self.runtime.private / 'incidents.sqlite'))
        sys.path.insert(0, str(self.runtime.root))
        from module.config.maintenance import WorkerLease
        self.Lease = WorkerLease
        self.groups = {}
        self.guard = threading.Lock()

    def deployment_lock(self):
        return FileLock(self.settings['deployment_lock'])

    def lease_state(self, name, pid):
        lease = self.Lease(self.runtime.root, name)
        try:
            state = json.loads(lease.state_path.read_text(encoding='utf-8'))
            if state['pid'] == pid and state['name'] == name:
                return state
        except (OSError, ValueError, KeyError):
            pass
        return {}

    def acquire_group(self, names):
        """Stop at a trustworthy scheduler wait; never interrupt active work."""
        locks = {}
        try:
            with self.deployment_lock():
                live = self.runtime.status()
                for name in names:
                    lease = self.Lease(self.runtime.root, name)
                    lease.lock.acquire(timeout=0)
                    locks[name] = lease.lock
                    if name in live and self.lease_state(name, live[name]).get('state') != 'idle':
                        raise Timeout('Worker has no current idle acknowledgment')
                if self.runtime.status() != live:
                    raise Timeout('Worker set changed during admission')
            return locks
        except Exception:
            for lock in locks.values():
                lock.release()
            raise

    def apply_plan(self, configs, failed, folder):
        now = datetime.now().replace(microsecond=0)
        changes, slots = plan_recovery(configs, failed, now)
        folder.mkdir(parents=True, exist_ok=True)
        for name in configs:
            shutil.copy2(self.runtime.root / 'config' / (name + '.json'), folder / (name + '.json'))
        (folder / 'schedule-plan.json').write_text(json.dumps({
            'changes': [(n, k, str(t)) for n, k, t in changes],
            'slots': [(n, str(t)) for n, t in slots]}, ensure_ascii=False, indent=2), encoding='utf-8')
        for name, key, stamp in changes:
            if self.runtime.set_value(name, key, 'scheduler', 'next_run', str(stamp), 'date_time') is not True:
                raise RuntimeError('Schedule update rejected')
            actual = self.runtime.configs()[name][key]['scheduler']['next_run']
            if actual != str(stamp):
                raise RuntimeError('Schedule update readback mismatch')
        return dict((name, stamp.timestamp()) for name, stamp in reversed(slots))

    def export_ai(self, row, reason):
        folder = self.runtime.private / 'ai' / row['id']
        folder.mkdir(parents=True, exist_ok=True)
        try:
            self.runtime.capture(self.runtime.configs()[row['name']]['script']['device'], folder / 'screen.png')
        except Exception:
            pass
        report = {'id': row['id'], 'profile': row['name'], 'reason': reason,
                  'log_tail': self.runtime.log_tail(row['name'], 160)}
        (folder / 'incident.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        self.store.update(row['id'], 'needs_ai', {'reason': reason, 'report': str(folder / 'incident.json')})

    def run_group(self, serial):
        locks = {}
        try:
            configs = self.runtime.configs()
            names = [n for n, c in configs.items() if c['script']['device']['serial'] == serial]
            # The receiver responds before a terminal worker has exited.
            time.sleep(3)
            while not locks:
                try:
                    locks = self.acquire_group(names)
                except Timeout:
                    time.sleep(5)
            rows = [r for r in self.store.rows(['queued']) if r['name'] in names]
            if not rows:
                return
            live = self.runtime.status()
            if any(r['name'] in live for r in rows):
                # A manual restart wins; do not stop it or create another worker.
                for row in rows:
                    if row['name'] in live:
                        self.store.update(row['id'], 'manual', {'reason': 'Profile already restarted externally'})
                rows = [r for r in rows if r['name'] not in live]
            if not rows:
                return
            failed = [r['name'] for r in rows]
            with self.deployment_lock():
                configs = self.runtime.configs()
                slots = self.apply_plan({n: configs[n] for n in names}, failed,
                                        self.runtime.private / 'backups' / rows[0]['id']) if len(names) > 1 else {}
            for row in rows:
                slots.setdefault(row['name'], min((t.timestamp() for t, _ in enabled_tasks(configs[row['name']])), default=time.time()))
                self.store.update(row['id'], 'waiting', {'not_before': slots[row['name']]})
            last_started = 0
            pending = list(rows)
            while pending:
                row = pending.pop(0)
                name = row['name']
                due = max(slots.get(name, min((t.timestamp() for t, _ in enabled_tasks(configs[name])), default=time.time())), last_started + (1800 if len(names) > 1 else 0))
                while time.time() < due:
                    time.sleep(min(5, due - time.time()))
                device = self.runtime.configs()[name]['script']['device']
                self.store.update(row['id'], 'diagnosing', {})
                with self.deployment_lock():
                    ready, evidence = self.runtime.probe(device)
                    if not ready:
                        # A working Android shell/capture excludes a demonstrated VM hang.
                        if any(e.get('shell') or e.get('adb_capture') for e in evidence):
                            raise RuntimeError('ADB/capture transport issue; VM hang is not established')
                        # Related live workers are frozen inside acknowledged idle leases.
                        # They cannot touch the VM until their locks are released.
                        self.runtime.restart_emulator(device)
                    self.runtime.capture_configured(device)
                    dismissed = self.runtime.dismiss_known_update(device)
                    locks[name].release()
                    locks.pop(name)
                    if name in self.runtime.status():
                        raise RuntimeError('Profile started externally during recovery')
                    self.runtime.control(name, 'start')
                    last_started = time.time()
                    recovery_pid = self.runtime.status()[name]
                    self.store.update(row['id'], 'running', {'started': last_started, 'dialog_dismissed': dismissed})
                while True:
                    live = self.runtime.status()
                    if name not in live:
                        if self.store.notified_since(row['id'], last_started):
                            self.export_ai(row, 'A new terminal notification ended the recovery attempt')
                        else:
                            self.store.update(row['id'], 'manual', {'reason': 'Stopped without a new terminal notification; no crash watchdog'})
                        break
                    if live[name] != recovery_pid:
                        self.store.update(row['id'], 'manual', {'reason': 'Worker replaced externally; relinquish control'})
                        break
                    state = self.lease_state(name, live[name])
                    if state.get('state') == 'idle':
                        lock = self.Lease(self.runtime.root, name).lock
                        try:
                            lock.acquire(timeout=0)
                        except Timeout:
                            time.sleep(2)
                            continue
                        locks[name] = lock
                        self.store.update(row['id'], 'recovered', {'pid': live[name], 'scheduler_idle': True,
                                                                  'log_tail': self.runtime.log_tail(name, 12)})
                        LOG.info('%s recovered and returned to scheduler wait', name)
                        break
                    # A newly selected Android user can expose its own native dialog.
                    try:
                        self.runtime.dismiss_known_update(device)
                    except Exception:
                        LOG.warning('Native dialog probe unavailable for %s', name)
                    time.sleep(5)
                # Even short batches remain at least 30 minutes apart on a shared VM.
            if len(names) > 1:
                while time.time() < last_started + 1800:
                    time.sleep(5)
                # If a long batch overran its reserved slot, postpone pending healthy
                # batches before releasing the admission locks. Do not change completed tasks.
                configs = self.runtime.configs()
                overdue = [n for n in names if n in self.runtime.status()
                           and any(t <= datetime.now() for t, _ in enabled_tasks(configs[n]))]
                if overdue:
                    with self.deployment_lock():
                        self.apply_plan({n: configs[n] for n in names}, overdue,
                                        self.runtime.private / 'backups' / (rows[0]['id'] + '-overrun'))
        except Exception as exc:
            LOG.exception('Recovery group %s paused', serial)
            for row in self.store.rows(['queued', 'waiting', 'diagnosing', 'running']):
                if self.runtime.configs().get(row['name'], {}).get('script', {}).get('device', {}).get('serial') == serial:
                    self.export_ai(row, str(exc))
        finally:
            # A failed diagnostic must not release competitors while a recovered
            # worker is still executing. This observes only this recovery cohort.
            while locks:
                try:
                    live = self.runtime.status()
                    active = [n for n in names if n not in locks and n in live
                              and self.lease_state(n, live[n]).get('state') != 'idle']
                    if not active:
                        break
                except Exception:
                    pass
                time.sleep(5)
            for lock in locks.values():
                lock.release()
            with self.guard:
                self.groups.pop(serial, None)

    def loop(self):
        # Interrupted recoveries require diagnosis, never blind replay of mutations.
        for row in self.store.rows(['waiting', 'diagnosing', 'running']):
            self.export_ai(row, 'Recovery service restarted during an unfinished operation')
        while True:
            try:
                configs = self.runtime.configs()
                for row in self.store.rows(['needs_ai']):
                    path = self.runtime.private / 'ai' / row['id'] / 'incident.json'
                    if not path.exists():
                        self.export_ai(row, 'Repeated terminal failure inside one-hour cooldown')
                for row in self.store.rows(['queued']):
                    serial = configs[row['name']]['script']['device']['serial']
                    with self.guard:
                        if serial not in self.groups:
                            worker = threading.Thread(target=self.run_group, args=(serial,), daemon=True)
                            self.groups[serial] = worker
                            worker.start()
            except Exception:
                LOG.exception('Receiver coordinator iteration failed')
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', required=True)
    args = parser.parse_args()
    settings = json.loads(Path(args.settings).read_text(encoding='utf-8-sig'))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    coordinator = Coordinator(settings)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path != '/health':
                self.send_error(404)
                return
            data = json.dumps({'ok': True, 'incidents': [{k: r[k] for k in ('id','name','state','updated')}
                                                       for r in coordinator.store.rows()]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if not secrets.compare_digest(self.path, '/notify/' + settings['token']):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 65536:
                    self.send_error(400)
                    return
                payload = json.loads(self.rfile.read(length))
                name = terminal_profile(payload, coordinator.runtime.configs())
                if name:
                    coordinator.store.add(name, payload)
                # Persist first and return 200 immediately; never await worker exit here.
                self.send_response(200)
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'{}')
            except Exception:
                LOG.exception('Invalid notification')
                self.send_error(500)
    with FileLock(str(coordinator.runtime.private / 'service.lock'), timeout=0):
        threading.Thread(target=coordinator.loop, daemon=True).start()
        ThreadingHTTPServer(('127.0.0.1', settings.get('port', 22389)), Handler).serve_forever()


if __name__ == '__main__':
    main()
