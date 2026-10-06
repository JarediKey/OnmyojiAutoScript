"""Prepare, resolve and validate an ordinary dev-to-prod merge without force pushes."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import time

IDENTITY = 'JarediKey'
EMAIL = 'JarediKey@users.noreply.github.com'
SHA = re.compile(r'[0-9a-f]{40}')
MARKER = re.compile(rb'^(<<<<<<< |=======\r?$|>>>>>>> )', re.MULTILINE)


def git(root, *args, check=True):
    return subprocess.run(['git', '-C', str(root), *args], check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def value(root, *args):
    return git(root, *args).stdout.decode().strip()


def paths(root, *args):
    return [p.decode('utf-8') for p in git(root, *args, '-z').stdout.split(b'\0') if p]


def identity(root):
    git(root, 'config', 'user.name', IDENTITY)
    git(root, 'config', 'user.email', EMAIL)
    git(root, 'config', 'commit.gpgsign', 'false')


def output(**items):
    for key, val in items.items():
        print(f'{key}={val}')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            for key, val in items.items():
                out.write(f'{key}={val}\n')


def check_sha(sha):
    if not SHA.fullmatch(sha):
        raise ValueError('Expected a full commit SHA')
    return sha


def begin(root, base, dev):
    check_sha(base); check_sha(dev)
    if value(root, 'status', '--porcelain'):
        raise RuntimeError('Candidate checkout must be clean')
    if value(root, 'rev-parse', 'HEAD') != base:
        raise RuntimeError('Candidate HEAD does not match the pinned prod revision')
    if git(root, 'merge-base', '--is-ancestor', dev, base, check=False).returncode == 0:
        return 'unchanged', []
    identity(root)
    result = git(root, 'merge', '--no-ff', '--no-commit', dev, check=False)
    conflicts = paths(root, 'diff', '--name-only', '--diff-filter=U')
    if conflicts:
        return 'conflict', conflicts
    if result.returncode:
        raise RuntimeError('Merge failed without conflicts: ' + result.stderr.decode(errors='replace'))
    return 'ready', []


def changed(root, base):
    return paths(root, 'diff', '--name-only', '--diff-filter=ACMR', base)


def check_files(root, base):
    for name in changed(root, base):
        p = root / name
        if p.is_symlink():
            raise RuntimeError(f'Changed symlink requires review: {name}')
        data = p.read_bytes()
        if name.endswith(('.py', '.json', '.md', '.yml', '.yaml', '.toml')) and MARKER.search(data):
            raise RuntimeError(f'Unresolved conflict marker: {name}')
        if name.endswith('.py'):
            ast.parse(data, filename=name)
        elif name.endswith('.json'):
            json.loads(data.decode('utf-8-sig'))
    # Check only introduced whitespace errors, not pre-existing files.
    git(root, 'diff', '--check', base)


def finish(root, base, dev, bundle):
    if paths(root, 'diff', '--name-only', '--diff-filter=U'):
        raise RuntimeError('Unmerged index remains')
    if value(root, 'rev-parse', 'HEAD') != base or value(root, 'rev-parse', 'MERGE_HEAD') != dev:
        raise RuntimeError('Merge identity changed')
    check_files(root, base)
    git(root, 'commit', '-m', f'Merge dev {dev[:12]} into prod')
    bundle.parent.mkdir(parents=True, exist_ok=True)
    git(root, 'bundle', 'create', str(bundle), 'HEAD', '^' + base, '^' + dev)
    output(candidate=value(root, 'rev-parse', 'HEAD'))


def fingerprint(root, names):
    result = {}
    for name in names:
        p = root / name
        if p.is_symlink():
            result[name] = ('symlink', os.readlink(p))
        elif p.exists():
            result[name] = ('file', hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mode & 0o777)
        else:
            result[name] = ('missing',)
    return result


def codex_environment():
    # Keep subscription credentials on the host; never pass GitHub/API tokens to Codex.
    keep = {'HOME', 'USER', 'LOGNAME', 'PATH', 'TMPDIR', 'LANG', 'LC_ALL',
            'CODEX_HOME', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'SYSTEMROOT', 'TEMP', 'TMP'}
    return {k: v for k, v in os.environ.items() if k in keep}


def resolve(root, base, dev, conflicts, prompt_file, log_dir, timeout=900):
    codex = os.environ.get('OAS_CODEX_BIN', 'codex')
    env = codex_environment()
    options = ['--ignore-user-config', '-c', 'forced_login_method="chatgpt"',
               '-c', 'model_provider="openai"']
    auth = subprocess.run([codex, 'login', 'status'], env=env, capture_output=True, text=True)
    if auth.returncode or 'Logged in using ChatGPT' not in auth.stdout + auth.stderr:
        raise RuntimeError('Codex must be logged in with ChatGPT; API-key fallback is forbidden')
    all_names = paths(root, 'ls-files')
    allowed = set(conflicts)
    for name in conflicts:
        if name.endswith('.json') and name.startswith('tasks/'):
            assets = str(Path(name).parent / 'assets.py')
            if assets in all_names:
                allowed.add(assets)
    before = fingerprint(root, set(all_names) - allowed)
    prompt = prompt_file.read_text(encoding='utf-8') + '\n\n' + json.dumps(
        {'prod_commit': base, 'dev_commit': dev, 'conflicts': conflicts,
         'editable_files': sorted(allowed)}, ensure_ascii=False)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_dir.chmod(0o700)
    log_path = log_dir / 'codex.jsonl'
    with log_path.open('wb') as log:
        log_path.chmod(0o600)
        proc = subprocess.Popen([codex, 'exec', *options, '--ephemeral', '--sandbox',
                                 'workspace-write', '-C', str(root), '--json', '-'],
                                env=env, stdin=subprocess.PIPE, stdout=log, stderr=log,
                                start_new_session=True)
        try:
            proc.communicate(prompt.encode(), timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            raise RuntimeError('Codex exceeded its 15-minute limit')
    if proc.returncode:
        raise RuntimeError(f'Codex failed (exit {proc.returncode}); private log: {log_path}')
    if before != fingerprint(root, before):
        raise RuntimeError('Codex changed files outside the permitted conflict scope')
    if paths(root, 'ls-files', '--others', '--exclude-standard'):
        raise RuntimeError('Codex created unexpected untracked files')
    if value(root, 'rev-parse', 'HEAD') != base:
        raise RuntimeError('Codex must not create or rewrite commits')
    git(root, 'add', '--', *sorted(allowed))
    if paths(root, 'diff', '--name-only', '--diff-filter=U'):
        raise RuntimeError('Codex left unresolved conflicts')


def inspect_bundle(root, base, dev, bundle):
    check_sha(base); check_sha(dev)
    git(root, 'bundle', 'verify', str(bundle))
    git(root, 'fetch', str(bundle), 'HEAD')
    candidate = value(root, 'rev-parse', 'FETCH_HEAD')
    parents = value(root, 'show', '-s', '--format=%P', candidate).split()
    if parents != [base, dev]:
        raise RuntimeError('Candidate does not merge the pinned prod/dev revisions')
    person = value(root, 'show', '-s', '--format=%an%n%ae%n%cn%n%ce', candidate).splitlines()
    if person != [IDENTITY, EMAIL, IDENTITY, EMAIL]:
        raise RuntimeError('Candidate author/committer mismatch')
    git(root, 'checkout', '--detach', candidate)
    check_files(root, base)
    output(candidate=candidate)


def smoke(root, prompt, logs):
    root.mkdir(parents=True, exist_ok=False)
    git(root, 'init', '-b', 'prod'); identity(root)
    p = root / 'settings.py'
    p.write_text('OPTIONS = {"upstream": 1, "custom": False}\n')
    git(root, 'add', '.'); git(root, 'commit', '-m', 'Fixture base')
    common = value(root, 'rev-parse', 'HEAD')
    p.write_text('OPTIONS = {"upstream": 1, "custom": True}\n')
    git(root, 'commit', '-am', 'Keep the custom prod setting')
    base = value(root, 'rev-parse', 'HEAD')
    git(root, 'checkout', '-b', 'dev', common)
    p.write_text('OPTIONS = {"upstream": 2, "custom": False}\n')
    git(root, 'commit', '-am', 'Update the upstream setting')
    dev = value(root, 'rev-parse', 'HEAD'); git(root, 'checkout', 'prod')
    state, conflicts = begin(root, base, dev)
    assert state == 'conflict'
    resolve(root, base, dev, conflicts, prompt, logs)
    parsed = ast.literal_eval(ast.parse(p.read_text()).body[0].value)
    if parsed != {'upstream': 2, 'custom': True}:
        raise RuntimeError('Smoke test did not preserve both intended changes')
    finish(root, base, dev, root.parent / 'smoke.bundle')
    print('PASS: subscription Codex resolved a real Git conflict and preserved both changes; no remote branch changed.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'resolve', 'inspect', 'smoke'])
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--base')
    parser.add_argument('--dev')
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--logs', type=Path)
    parser.add_argument('--prompt', type=Path, default=Path(__file__).parents[1] / 'codex/resolve-prod.md')
    args = parser.parse_args()
    root = args.repo.resolve()
    if args.command == 'smoke':
        smoke(root, args.prompt, args.logs.resolve()); return
    base = args.base or value(root, 'rev-parse', 'HEAD')
    dev = args.dev or value(root, 'rev-parse', 'origin/dev')
    if args.command == 'inspect':
        inspect_bundle(root, base, dev, args.bundle.resolve()); return
    state, conflicts = begin(root, base, dev)
    output(state=state, base=base, dev=dev)
    if args.command == 'resolve':
        if state != 'conflict':
            raise RuntimeError('Pinned revisions no longer reproduce the expected conflict')
        state_dir = Path(os.environ['OAS_AUTOMATION_STATE']) / 'attempts'
        state_dir.mkdir(parents=True, exist_ok=True)
        attempt = state_dir / f'{base}-{dev}.json'
        cached = state_dir / f'{base}-{dev}.bundle'
        if attempt.exists() and os.environ.get('OAS_RETRY_AI') != '1':
            if cached.exists():
                args.bundle.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cached, args.bundle)
                print('Reusing a completed AI candidate; no additional subscription usage.')
                return
            raise RuntimeError('This revision pair already used its AI attempt; manually dispatch with retry_ai=true to retry')
        attempt.write_text(json.dumps({'base': base, 'dev': dev, 'started': time.time()}))
        resolve(root, base, dev, conflicts, args.prompt, args.logs.resolve())
        finish(root, base, dev, args.bundle.resolve())
        shutil.copy2(args.bundle, cached)
        return
    if state == 'ready':
        finish(root, base, dev, args.bundle.resolve())
    elif conflicts:
        print('Conflicts: ' + ', '.join(conflicts))


if __name__ == '__main__':
    main()
