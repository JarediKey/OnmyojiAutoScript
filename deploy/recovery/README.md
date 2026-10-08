# Terminal-notification recovery

[简体中文](README.zh.md)

This independent controller uses OAS notifications and existing configuration,
WebSocket and maintenance APIs. OAS must include the blocking profile-start lease
introduced in `8d080403`. It is not a worker-crash watchdog.

## Behavior

- Accept OnePush Custom JSON POSTs on a token-protected loopback URL. Persist
  terminal events before returning HTTP 200; recovery happens asynchronously.
- `RequestHumanTakeover`, `ScriptError`, unhandled exceptions and three failed
  attempts qualify. Normal retries, idle states and unnotified/manual stops do not.
- Deduplicate active incidents. A repeated terminal failure within one hour goes
  to the private AI queue instead of another immediate restart.
- Probe Android shell/boot and decoded 1280×720 ADB captures up to three times,
  five seconds apart, with command timeouts and one targeted reconnect. A working
  channel does not establish a frozen VM. Probe the configured ADB or Nemu IPC
  screenshot backend before restarting an OAS profile.
- A private, visually approved native engine-update dialog template may dismiss
  only its exact “Not now” button, with 0.985 correlation and disappearance checks.
  No template means no automatic UI click. Monitor this dialog throughout a
  recovery attempt because restarting the game can show it again.
- When both Android channels consistently fail, restart only the validated MuMu
  instance. Use the manager first; terminate only surviving per-instance device
  processes whose executable and `--vm` identity match. Never kill global ADB,
  MuMu services or other VMs. Require boot, ADB capture and configured capture
  before starting the failed profile. Related live workers remain frozen inside
  their acknowledged scheduler waits throughout the restart.
- For shared-VM recovery, leave healthy active work alone. Reserve overdue failed
  profiles in 30-minute batches, keep a profile's pending tasks together, and
  cascade only colliding upcoming batches. Back up settings, change only
  `next_run`, and verify each write. Actual profile locks prevent overlapping
  execution if a batch overruns. Completed tasks and recurring rules are retained.
  Event tasks that have expired still follow the task's normal scheduling rules.
- Respect externally replaced workers. A live PID alone is not completion:
  recovery is complete only after the worker returns to its scheduler wait.

## Private AI consumer

The Mac consumer polls only the private incident queue over SSH once per minute.
It invokes `codex exec` only for actionable incidents, reusing the saved ChatGPT
login and removing API-key environment overrides. There is one structured,
read-only diagnosis per incident. The model can request one controller-guarded
retry or human intervention. It cannot issue arbitrary process-kill commands or
silently patch/publish source. Source defects currently require human review.
Only unresolved incidents produce a local desktop notification. Logs, decisions,
notification tokens and account backups stay private, outside GitHub.
The Mac must be awake and able to reach Ebony over SSH. AI incidents remain queued
while it is unavailable; deterministic recovery on Ebony can still run.

## Runtime layout

Keep the installed Python files in a private `recovery/code/` directory and
`settings.json` beside it. The Windows settings contain `root`, `private`,
`deployment_lock`, `oas_port`, `port` and a randomly generated `token`. Run
`service.py --settings <path>` with OAS's Python in the logged-in desktop session.
Use a Scheduled Task at logon, with separate redirected stdout/stderr files;
PowerShell's error stream must not terminate Python's ordinary log output.

Set each profile's `script.error.notify_enable=true` and `notify_config` to:

```yaml
provider: custom
url: http://127.0.0.1:22389/notify/REPLACE_WITH_PRIVATE_TOKEN
method: post
data: {}
```

Back up existing notification settings before replacement. Test the installed
OnePush provider with a nonterminal message first. The receiver's `/health` is
read-only. Import historical terminal failures only through an explicit operator
seed; startup does not scan absent workers and restart them.

The Mac settings contain `host`, `user`, `ssh_key`, `hostkey_alias`, `private` and
`codex`. Run `codex_worker.py --settings <path>` from a launchd job every minute.
`incidentctl.py` supports fixed private SSH operations; account configuration is
never exported. Interrupted operations require diagnosis instead of blind replay.

The controller is installed as a pinned private copy, separately from OAS code
activation. Replace it only after checking active recovery cohorts; preserve its
SQLite queue, settings and backups. Stopping its Windows task disables recovery;
disable the Mac launchd job to stop AI consumption. Normal OAS retries continue.

## Verification

Run `python -m unittest discover -s deploy/recovery -p 'test_*.py' -v`, plus the
maintenance lease/API and safe-update tests. Real approved-dialog positive and
courtyard-negative screenshots can be replayed privately. Do not restart a healthy
production emulator just to test the forced-restart path. Real emulator restart
and boot verification need a supervised fault or isolated VM test before being
reported as live-verified.
