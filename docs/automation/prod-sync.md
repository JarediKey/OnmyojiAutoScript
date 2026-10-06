# Automatic dev-to-prod synchronization

[简体中文](prod-sync.zh.md)

`Sync Upstream Branches` lives on the default `master` branch. It runs daily at
04:17 UTC (12:17 Asia/Shanghai) and supports manual dispatch. Scheduled start times
can be delayed by GitHub. Source `runhey/dev` is mirrored exactly to `origin/dev`;
the workflow then attempts an ordinary merge into `origin/prod`. `master` is
independently merged from `runhey/master`; its failure does not cancel prod work.
This workflow never deploys Ebony or restarts account processes.

## Execution and publication

1. The GitHub-hosted prepare job pins prod/dev commits. Already-integrated dev
   revisions finish without AI or publication. A Git error without unmerged
   files fails instead of triggering AI.
2. A genuine merge conflict dispatches to the local Runner labelled
   `oas-codex-subscription`. It runs `codex exec` with saved ChatGPT authentication,
   ignores user provider configuration, forces ChatGPT/OpenAI authentication, and
   excludes API keys and GitHub tokens from the Codex environment. Subscription
   limits still apply; expired login or exhausted allowance fails the attempt.
   There is no automatic API-key fallback. The desktop app need not remain open.
3. AI may modify the conflict files and corresponding generated task assets only.
   It cannot publish. The controller checks scope, index, syntax/JSON, conflict
   markers, handwritten-code whitespace and merge identity, then builds a Git bundle.
   Upstream-generated asset whitespace is reported but does not block publication.
4. A fresh GitHub-hosted Windows job verifies the bundle and runs the offline
   regression suite. A separate write-enabled job rechecks remote branch tips,
   author/committer, and merge parents before a normal push. Concurrent changes
   cause a failed publication, not a force push; the next sync prepares anew.
   Offline checks do not prove every in-game state or Ebony-only patch works.

## Runner operation

Use the official GitHub Actions Runner on the authorized Mac account. Install
`.github/scripts/runner-guard.sh` outside its checkout/application directory and
set `ACTIONS_RUNNER_HOOK_JOB_STARTED` to that absolute path. The hook accepts only
this repository's `master` version of `sync-upstream.yml`, schedule/manual events,
and the `resolve_conflict` or `runner_smoke` jobs. Do not enable fork/PR execution
on this runner. A personal self-hosted runner remains a trusted machine, not a
sandbox for arbitrary repository code; administrators must protect workflow edits.

Set these host environment entries in the Runner's `.env` file:

- `OAS_CODEX_BIN`: absolute path to the approved Codex CLI.
- `OAS_PYTHON_BIN`: absolute path to Python 3.10 or newer.
- `OAS_AUTOMATION_STATE`: private host directory for attempt records and logs.
- `ACTIONS_RUNNER_HOOK_JOB_STARTED`: absolute path to the installed guard.

Log in with `codex login` as the same OS user, then verify `codex login status`
reports ChatGPT. Keep credentials on the host. Register the runner in repository
Settings → Actions → Runners using GitHub's short-lived registration token; do not
commit tokens, `.credentials`, `.runner`, Codex logs, or login files. Install/start
GitHub's `svc.sh` service for the logged-in Mac user. The Mac must remain awake and
online. GitHub queues jobs while it is unavailable, but a queue older than 24 hours
fails. The next scheduled/manual sync can retry an unstarted job.

## Controls and diagnostics

- Manual `mode=sync` runs the normal synchronization chain.
- Manual `mode=ai-smoke` dispatches a real isolated Git conflict to local Codex and
  validates both resulting settings. It also runs the current prod baseline's
  Windows regression suite. Neither branch synchronization nor publication runs.
- The AI subprocess has a 15-minute limit; its job has a 20-minute limit. Each
  pinned prod/dev pair gets one AI attempt recorded on the Mac. Subsequent runs
  reuse a completed bundle or fail without another AI call. For an intentional
  retry after investigating a failure, manually dispatch with `retry_ai=true`.
- Private Codex output stays under the host state directory; only the candidate
  bundle is uploaded, for seven days. Actions job logs and the workflow summary
  show statuses and pinned revisions. GitHub's normal workflow-failure notification
  preferences apply; no separate email or desktop notification service is added.
- Stop the runner with `svc.sh stop`. Disabling this workflow stops its scheduled
  branch updates. Existing prod and Ebony processes remain unchanged on failure.

## Verification

Run `python .github/scripts/test_prod_sync.py` for isolated real-Git checks covering
no-op/clean/conflicting merges, errors, dirty/stale candidates, invalid resolutions,
bundle ancestry/identity and runner admission. Use the manual smoke mode to verify
GitHub → Mac → subscription Codex and the Windows validation environment together.

References: [GitHub runners](https://docs.github.com/en/actions/reference/runners/self-hosted-runners),
[runner hooks](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/run-scripts),
[Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode),
[Codex authentication](https://learn.chatgpt.com/docs/auth).
