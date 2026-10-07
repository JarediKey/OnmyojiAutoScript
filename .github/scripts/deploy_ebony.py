"""Dispatch the host's idle updater; disconnecting SSH must not kill deployment."""
import base64
import json
import os
from pathlib import Path
import subprocess


def ps_quote(value):
    return "'" + value.replace("'", "''") + "'"


def main():
    host = os.environ['OAS_EBONY_HOST']
    user = os.environ['OAS_EBONY_USER']
    key = os.environ['OAS_EBONY_SSH_KEY']
    alias = os.environ['OAS_EBONY_HOSTKEY_ALIAS']
    folder = os.environ['OAS_EBONY_AUTOMATION']
    script = """$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$task=Get-ScheduledTask -TaskName 'OAS-Safe-Update'
if($task.State -eq 'Running'){
 Write-Output '{"status":"deferred","reason":"Host updater already running"}'
 exit 0
}
$previous=(Get-ScheduledTaskInfo -TaskName 'OAS-Safe-Update').LastRunTime
Start-ScheduledTask -TaskName 'OAS-Safe-Update'
$started=$false
for($attempt=0;$attempt -lt 15;$attempt++){
 Start-Sleep -Seconds 1
 if((Get-ScheduledTaskInfo -TaskName 'OAS-Safe-Update').LastRunTime -gt $previous){$started=$true;break}
}
if(-not $started){
 Write-Output '{"status":"deferred","reason":"Desktop session is unavailable; host task has not started"}'
 exit 0
}
while((Get-ScheduledTask -TaskName 'OAS-Safe-Update').State -eq 'Running'){Start-Sleep -Seconds 5}
Get-Content -LiteralPath LOG_PATH
if((Get-ScheduledTaskInfo -TaskName 'OAS-Safe-Update').LastTaskResult -ne 0){exit 1}
""".replace('LOG_PATH', ps_quote(folder.rstrip('\\/') + '\\last-update.log'))
    command = ['ssh', '-i', key, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'HostKeyAlias=' + alias,
               user + '@' + host, 'powershell', '-NoProfile', '-NonInteractive',
               '-EncodedCommand', base64.b64encode(script.encode('utf-16le')).decode()]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45 * 60)
    private_log = Path(os.environ['OAS_AUTOMATION_STATE']) / 'logs' / ('deploy-' + os.environ.get('GITHUB_RUN_ID', 'manual') + '.log')
    private_log.parent.mkdir(parents=True, exist_ok=True)
    private_log.write_text(result.stdout + result.stderr, encoding='utf-8')
    private_log.chmod(0o600)
    records = []
    for line in result.stdout.splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict) and 'status' in item:
                records.append(item)
                print(json.dumps(item, ensure_ascii=False), flush=True)
        except ValueError:
            pass
    if not records:
        # Keep private transport details out of a public repository's logs.
        raise RuntimeError('No deployment report received; inspect the private Runner/host task logs')
    final = records[-1]
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write('### Ebony deployment\n\n```json\n' + json.dumps(final, ensure_ascii=False, indent=2) + '\n```\n')
    if result.returncode or final['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
