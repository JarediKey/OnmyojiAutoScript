# OAS repository instructions

## Branch ownership

- `origin` is `https://github.com/JarediKey/OnmyojiAutoScript.git`;
  `runhey` is `https://github.com/runhey/OnmyojiAutoScript.git`.
- Fetch both remotes before comparisons or work requiring current upstream.
- `dev` mirrors `runhey/dev`. Do not put personal commits there; the daily
  synchronization workflow force-aligns the remote branch.
- `master` tracks `origin/master`, which merges `runhey/master` and retains
  the fork's synchronization workflow. Do not reset it to upstream master.
- `prod` tracks `origin/prod` and contains selected personal changes plus the
  upstream development baseline. Update it through ordinary merges from current
  `runhey/dev` and approved work branches. Review conflicts and validate before
  pushing. Never rebase or force-sync published `prod`.
- Create focused `feature/*`, `fix/*`, `refactor/*`, or `chore/*` branches
  from current `runhey/dev`. Use current `prod` instead when a task depends on
  prod-only changes. Do not create `codex/*` branches.
- Preserve `archive/*` and `archive-QML` as historical references. Port only
  needed behavior; do not merge or rebase an archive wholesale.
- Push validated task changes to their matching branch on `origin`, as requested
  by Jared. Promote to `prod` when the task authorizes that integration.
  Publishing a work branch alone is not a production deployment.
- Upstream contributions target `runhey/dev`. Do not push to `runhey`, open
  upstream PRs, or delete remote branches without explicit authorization.

## Implementation and verification

- Reuse shared components in `module/` and `tasks/Component/`.
- Regenerate task `assets.py` through `dev_tools/assets_extract.py`; edit the
  source JSON and image assets, not generated Python declarations.
- Synchronize affected task models, menu/scheduler registration, templates,
  localization, and documented behavior.
- `1280x720` landscape is the image-coordinate contract. Revalidate templates,
  OCR regions, thresholds, and click regions against the relevant game UI.
- Preserve local environments, logs, screenshots, and instance configurations.
  Separate framework changes from task-specific asset updates.
- Inspect status/diffs before and after edits, run `git diff --check`, and use
  focused syntax, import, or behavioral checks for changed Python code.
- For scheduling, trace `next_run`, success/failure intervals, explicit targets,
  and server-time overrides instead of relying on log wording.
- Distinguish static/mocked checks from emulator verification; state untested
  UI states, game modes, emulator backends, and account roles.
