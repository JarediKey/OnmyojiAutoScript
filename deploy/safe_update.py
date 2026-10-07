"""Stage and activate prod during an acknowledged idle window on a Windows host."""
import argparse
import asyncio
from datetime import datetime, time as day_time, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import quote
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from filelock import FileLock, Timeout
import psutil
from module.config.maintenance import DeploymentBusy, acquire_idle_workers

BEIJING = timezone(timedelta(hours=8))


def in_window(now=None):
    now = now or datetime.now(BEIJING)
    return day_time(8, 10) <= now.astimezone(BEIJING).time() < day_time(8, 50)


def run(args, cwd=None, env=None, timeout=120):
    return subprocess.run(list(map(str, args)), cwd=cwd, env=env, timeout=timeout,
                          check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')


def git(root, *args):
    return run(['git', '-C', root, *args]).stdout.strip()


def report(status, **details):
    print(json.dumps({'status': status, **details}, ensure_ascii=False), flush=True)


def status(port):
    try:
        with urlopen(f'http://127.0.0.1:{port}/maintenance/status', timeout=3) as response:
            data = json.load(response)
    except Exception as exc:
        raise DeploymentBusy('Backend is offline or does not support safe deployment yet') from exc
    if data.get('version') != 1:
        raise DeploymentBusy('Unsupported maintenance protocol')
    return data


def config_hashes(root):
    files = list((root / 'config').rglob('*.json')) + [root / 'config/deploy.yaml']
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files if p.exists() and p.name != 'template.json'}


def check_process(root, pid):
    process = psutil.Process(pid)
    if Path(process.cwd()).resolve() != root.resolve():
        raise RuntimeError('Listener process has an unexpected working directory')
    if Path(process.exe()).resolve() != (root / 'toolkit/python.exe').resolve():
        raise RuntimeError('Listener is not the expected OAS Python runtime')
    if not any(Path(arg).name == 'server.py' for arg in process.cmdline()):
        raise RuntimeError('Listener is not the OAS backend')
    return process


def stop_backend(process):
    runtime = Path(process.exe()).parent
    children = []
    for child in process.children(recursive=True):
        try:
            executable = Path(child.exe())
            if executable.parent == runtime and executable.name.lower() in ('python.exe', 'pythonw.exe'):
                children.append(child)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # Keep emulator/ADB descendants alive; only OAS Python processes are owned.
    # Workers have acknowledged idle and are reserved before this is called.
    for child in children:
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    process.terminate()
    _, alive = psutil.wait_procs(children + [process], timeout=3)
    for child in alive:
        child.kill()
    _, alive = psutil.wait_procs(alive, timeout=3)
    if alive:
        raise RuntimeError('OAS process tree did not stop; source was not changed')


def start_backend(settings):
    task = settings['launcher_task']
    if not task.replace('-', '').isalnum():
        raise ValueError('Unexpected launcher task name')
    run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
         "Start-ScheduledTask -TaskName '" + task + "'"], timeout=10)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            value = status(settings['port'])
            if value['workers']:
                raise RuntimeError('Managed launcher unexpectedly started account workers')
            return value
        except DeploymentBusy:
            time.sleep(.5)
    raise RuntimeError('New backend failed its health check before account startup')


async def restore_workers(port, names):
    import websockets
    async def start(name):
        async with websockets.connect(f'ws://127.0.0.1:{port}/ws/{quote(name)}') as ws:
            await ws.send('start')
            while True:
                data = json.loads(await ws.recv())
                if data.get('state') == 1:
                    return
    await asyncio.wait_for(asyncio.gather(*(start(name) for name in names)), timeout=20)
    live = status(port)['workers']
    if not set(names) <= set(live):
        raise RuntimeError('Not all previously running workers are alive after activation')


def prepare(settings, old, revision):
    root = Path(settings['root']); python = root / 'toolkit/python.exe'
    backup = Path(settings['backup_root']) / ('auto-deploy-' + revision[:12])
    backup.mkdir(parents=True, exist_ok=True)
    candidate = backup / 'candidate'
    if not candidate.exists():
        git(root, 'worktree', 'add', '--detach', str(candidate), revision)
    if git(candidate, 'rev-parse', 'HEAD') != revision or git(candidate, 'status', '--porcelain', '--untracked-files=no'):
        raise RuntimeError('Staged candidate was modified')
    changed = git(root, 'diff', '--name-only', old, revision).splitlines()
    if any(p in ('requirements.txt', 'requirements-in.txt') or p.startswith('toolkit/') for p in changed):
        raise RuntimeError('Runtime dependencies changed; update the runtime before automatic activation')
    if any(p.startswith('config/') and p != 'config/template.json' for p in changed):
        raise RuntimeError('Tracked private/deployment configuration change requires manual review')
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    env['PYTHONPATH'] = settings['test_pythonpath']
    validated = backup / 'validated.json'
    if not validated.exists():
        args = [python, '-m', 'pytest', '-q', 'tests', 'tasks/FrogBoss/test_frog_oas.py',
                'tasks/FrogBoss/test_betting_flow.py']
        result = subprocess.run(list(map(str, args)), cwd=candidate, env=env,
                                capture_output=True, timeout=600)
        (backup / 'tests.txt').write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError('Staged regression tests failed; live processes were not touched')
        if git(candidate, 'status', '--porcelain', '--untracked-files=no'):
            raise RuntimeError('Tests modified tracked candidate source')
        validated.write_text(json.dumps({'revision': revision}), encoding='utf-8')
    elif json.loads(validated.read_text())['revision'] != revision:
        raise RuntimeError('Validation stamp does not match the candidate')
    # Validate current private models in memory; do not copy them into Git or save them.
    model_probe = """import json,sys
from pathlib import Path
from module.config.config_model import ConfigModel
from unittest.mock import patch
files=[p for p in (Path(sys.argv[1])/'config').glob('*.json') if p.stem!='template']
for p in files:
    with patch.object(ConfigModel, 'read_json', return_value=json.loads(p.read_text(encoding='utf-8-sig'))), patch.object(ConfigModel, 'write_json', side_effect=RuntimeError('Model validation must not save configuration')):
        ConfigModel(p.stem)
print('Validated',len(files),'account models without configuration writes')
"""
    try:
        run([python, '-c', model_probe, root], cwd=candidate, env=env, timeout=60)
    except subprocess.CalledProcessError as exc:
        (backup / 'model-check.txt').write_text((exc.stdout or '') + (exc.stderr or ''), encoding='utf-8')
        raise RuntimeError('Account model validation failed; details remain in the private host backup') from exc
    report('prepared', revision=revision, model_validation='passed')
    return backup


def activate(settings, old, revision, backup):
    root = Path(settings['root']); port = settings['port']
    observed = status(port)
    process = check_process(root, observed['backend_pid'])
    workers = observed['workers']
    with acquire_idle_workers(root, workers, minimum_seconds=180):
        if not in_window():
            raise DeploymentBusy('Deployment window has ended')
        if status(port) != observed:
            raise DeploymentBusy('Worker roster changed during idle admission')
        if git(root, 'rev-parse', 'HEAD') != old or git(root, 'status', '--porcelain', '--untracked-files=no'):
            raise DeploymentBusy('Live source changed while the candidate was prepared')
        hashes = config_hashes(root)
        snapshot = backup / ('activation-' + datetime.now(BEIJING).strftime('%Y%m%d-%H%M%S'))
        snapshot.mkdir()
        shutil.copytree(root / 'config', snapshot / 'config')
        (snapshot / 'before.json').write_text(json.dumps({'old': old, 'revision': revision,
            'workers': workers, 'config_hashes': hashes}), encoding='utf-8')
        stopped = False
        try:
            stopped = True
            stop_backend(process)
            run(['git', '-C', root, 'merge', '--ff-only', revision], timeout=15)
            if config_hashes(root) != hashes:
                raise RuntimeError('Account/deployment configuration changed during source activation')
            ready = start_backend(settings)
            check_process(root, ready['backend_pid'])
        except Exception:
            # Rollback is allowed only before any new account workers are started.
            if stopped:
                pid_file = Path(settings['backend_pidfile'])
                if pid_file.exists():
                    pid = int(pid_file.read_text(encoding='utf-8-sig').strip())
                    try:
                        failed = check_process(root, pid)
                        if '--run-none' not in failed.cmdline():
                            raise RuntimeError('Unexpected backend prevents rollback')
                        stop_backend(failed)
                    except psutil.NoSuchProcess:
                        pass
                run(['git', '-C', root, 'checkout', '--detach', old], timeout=15)
                start_backend(settings)
                asyncio.run(restore_workers(port, sorted(workers)))
            raise
    asyncio.run(restore_workers(port, sorted(workers)))
    report('deployed', revision=revision, restored_workers=len(workers))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--wait', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    settings = json.loads(args.settings.read_text(encoding='utf-8-sig'))
    root = Path(settings['root']).resolve()
    settings['root'] = str(root)
    state = Path(settings['backup_root'])
    state.mkdir(parents=True, exist_ok=True)
    with FileLock(str(state / 'auto-deploy.lock'), timeout=0):
        if not args.prepare_only and not in_window():
            report('deferred', reason='Outside 08:10-08:50 Asia/Shanghai'); return
        old = git(root, 'rev-parse', 'HEAD')
        git(root, 'fetch', 'origin', 'prod')
        revision = git(root, 'rev-parse', 'origin/prod')
        if old == revision:
            report('up_to_date', revision=revision); return
        git(root, 'merge-base', '--is-ancestor', old, revision)
        if git(root, 'status', '--porcelain', '--untracked-files=no'):
            raise RuntimeError('Unpublished source changes block deployment; preserve and publish them first')
        backup = prepare(settings, old, revision)
        if args.prepare_only:
            return
        while in_window():
            try:
                activate(settings, old, revision, backup)
                return
            except DeploymentBusy as exc:
                report('deferred', reason=str(exc))
                if not args.wait:
                    return
                time.sleep(30)
        report('deferred', reason='No safe idle opportunity before 08:50 Asia/Shanghai')


if __name__ == '__main__':
    try:
        main()
    except Timeout:
        report('deferred', reason='Another deployment controller is already running')
    except Exception as exc:
        report('failed', reason=str(exc))
        raise SystemExit(1)
