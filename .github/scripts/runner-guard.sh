#!/bin/bash
set -eu
# This hook is installed outside the runner checkout and runs before job steps.
test "${GITHUB_REPOSITORY:-}" = 'JarediKey/OnmyojiAutoScript'
test "${GITHUB_REF:-}" = 'refs/heads/master'
test "${GITHUB_WORKFLOW_REF:-}" = 'JarediKey/OnmyojiAutoScript/.github/workflows/sync-upstream.yml@refs/heads/master'
case "${GITHUB_EVENT_NAME:-}" in schedule|workflow_dispatch) ;; *) exit 1 ;; esac
case "${GITHUB_JOB:-}" in resolve_conflict|runner_smoke|deploy_ebony) ;; *) exit 1 ;; esac
printf '%s\n' 'Accepted trusted OAS subscription-Codex job.'
