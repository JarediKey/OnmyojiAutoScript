"""Dispatch the trusted workflow once per UTC day from the Mac login session."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess

REPOSITORY = 'JarediKey/OnmyojiAutoScript'


def run_cli(gh, *args):
    env = {k: v for k, v in os.environ.items() if k not in ('GH_TOKEN', 'GITHUB_TOKEN')}
    env['GH_PROMPT_DISABLED'] = '1'
    return subprocess.run([str(gh), *args], env=env, check=True, capture_output=True,
                          text=True, timeout=30).stdout


def dispatch(gh, state, now, force=False):
    now = now.astimezone(timezone.utc)
    if not force and not (now.hour == 0 and 10 <= now.minute < 50):
        return None
    state.mkdir(parents=True, exist_ok=True)
    state.chmod(0o700)
    with (state / 'dispatch.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        path = state / (now.date().isoformat() + '.json')
        old = json.loads(path.read_text()) if path.exists() else {}
        if old.get('status') == 'dispatched':
            return None
        try:
            account = json.loads(run_cli(gh, 'api', 'user', '--hostname', 'github.com'))
            if account.get('login') != 'JarediKey':
                raise ValueError('GitHub CLI must be logged in as JarediKey')
            runs = json.loads(run_cli(gh, 'api', '--hostname', 'github.com',
                'repos/' + REPOSITORY + '/actions/workflows/sync-upstream.yml/runs'
                '?event=workflow_dispatch&per_page=20'))['workflow_runs']
            existing = next((r for r in runs if r.get('head_branch') == 'master'
                and r.get('display_title') == 'OAS workflow_dispatch sync'
                and datetime.fromisoformat(r['created_at'].replace('Z', '+00:00')).date()
                == now.date()), None)
            if existing is None:
                run_cli(gh, 'workflow', 'run', 'sync-upstream.yml', '--repo', REPOSITORY,
                        '--ref', 'master', '--field', 'mode=sync')
            result = {'status': 'dispatched', 'date': str(now.date()),
                      'existing_run': existing['id'] if existing else None}
        except (subprocess.SubprocessError, OSError, ValueError, KeyError) as exc:
            # A lost dispatch response is reconciled against GitHub on the next tick.
            result = {'status': 'blocked', 'date': str(now.date()),
                      'reason': str(exc) if isinstance(exc, ValueError) else type(exc).__name__}
        pending = path.with_suffix('.tmp')
        pending.write_text(json.dumps(result), encoding='utf-8')
        pending.chmod(0o600)
        pending.replace(path)
        return result if result != old else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gh', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    result = dispatch(args.gh, args.state, datetime.now(timezone.utc), args.force)
    if result:
        print(json.dumps(result), flush=True)
    if result and result['status'] == 'blocked':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
