# Idle deployment on Windows

[简体中文](safe-update.zh.md)

`deploy/safe_update.py` stages the current published `origin/prod` and switches
source only when every live worker acknowledges a safe scheduler wait. It does
not stop a running task based on the UI's RUNNING flag or inferred log timing.
This controller does not use AI or API credentials.

## Admission and activation

Workers hold an OS-backed file lock while doing work, including idle cleanup,
game closing and emulator startup. Only `Script.wait_until` releases that lock.
Its acknowledgment includes PID, configuration digest and next wake time. The
controller acquires all account locks without waiting, rejects stale identities,
changed settings and wakes less than three minutes away, and holds the locks
through activation. An admission lock prevents new workers entering game code.
A busy worker makes the update defer immediately; its task is not terminated.

The deployment window is 08:10 inclusive to 08:50 exclusive in Asia/Shanghai.
`--wait` retries busy admission every 30 seconds within that window. If GitHub
finishes later, the host is unavailable, or no idle opportunity exists, deployment
waits for a later invocation. No task is disabled or rescheduled to create a gap.

Download and the complete offline regression suite run in an isolated worktree
before admission. Current account models are validated in memory. Unpublished
tracked changes, divergent history, runtime dependency changes, and tracked
private/deployment configuration changes block automatic deployment. They require
review rather than a force reset. Test logs and private configuration snapshots
remain in the host's backup directory.

After admission the controller backs up configurations, stops only the verified
OAS backend and its bundled-Python descendants (leaving emulator/ADB processes
alive), performs a fast-forward, verifies configuration hashes,
and launches the backend in the interactive desktop session with `--run-none`.
Only after its health check succeeds are the previously live account workers
started through the existing WebSocket API. Previously stopped/crashed workers
are not silently started. The source swap has a 15-second timeout, backend startup
has a 20-second health deadline, and worker startup is concurrent with a 20-second
limit. Download/testing are outside this interruption of the idle backend.

If source activation or backend health fails before account startup, the controller
checks the managed launcher's exact PID, returns to the previous revision and
restores the prior workers. Once new account workers have started, a failure is
reported without an automatic rollback that could interrupt their tasks.

## Host setup

Run the controller with the bundled Windows Python from the OAS repository root:

```powershell
.\toolkit\python.exe deploy\safe_update.py --settings D:\Onmyoji\automation\deploy.json --wait
```

The private settings JSON contains `root`, `backup_root`, `port`, `launcher_task`,
`backend_pidfile`, and `test_pythonpath`. The test path points to installed test-only
dependencies; the production launcher must not inherit it. The launcher is a
manual-only Windows Scheduled Task for the logged-in user, runs hidden
`toolkit\python.exe server.py --run-none` from `root`, and writes the child PID to
`backend_pidfile`. Use the desktop session for MuMu IPC, never SSH session 0. Git trusts only the
explicitly configured checkout path per command; no global wildcard trust is set.

`GET /maintenance/status` returns only actual live workers and backend PID to
loopback clients. It rejects remote clients. The `--run-none` startup option
explicitly overrides both the CLI run list and deployment-configured run list.

The first installation requires an independently verified idle restart to load
the worker lease code. Old workers cannot acknowledge this protocol and are
rejected; the automatic controller has no legacy force-stop fallback. Preserve
private configuration and any approved local source patches during initialization.

`--prepare-only` validates a candidate without process/source activation, even
outside the window. The controller reports `up_to_date`, `prepared`, `deferred`,
`deployed` or `failed` as JSON. Inspect the report, not just the process exit code:
deferral is a normal successful outcome, not proof that a revision was deployed.
