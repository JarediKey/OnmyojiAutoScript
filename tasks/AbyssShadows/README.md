# Abyss Shadows

[简体中文](README.zh.md)

The task supports ordered region/enemy targets, independent soul preloading,
locked lineups, and natural/timed/damage-based battle objectives. It uses shared
navigation and the account's global skin settings. Publication of the code does
not update an existing production checkout or private instance configuration.

## First trial configuration

The portable task section is [abyss-trial.json](../../deploy/examples/abyss-trial.json).
Use a separate checkout/configuration directory; do not add it to the live
production backend, whose older schema does not understand the new fields.

- Prepare four separate trial configs by copying each account's device/global
  settings locally on the production host. Disable every task except Abyss in
  each config.
  Leave the trial backend and all four instances stopped.
  Use a separate backend port, 22289, with automatic
  updates/dependency installation disabled. Do not start both controllers on
  the same emulator; stop the matching production instance before any trial.
- Enter the activity manually, record the emulator, then start the pilot on
  Friday/Saturday/Sunday. The trial does not enable or select activity difficulty.
- `attack_order: A` tests Dragon only. In legacy notation a region expands to
  elites 4/5/6, generals 2/3, then boss 1. Explicit targets such as
  `A-1;A-2;A-3;A-4;A-5;A-6` can change that order. A/B/C/D map to
  Dragon/Peacock/Fox/Leopard. Separate tokens with semicolons, not `>`.
- All strategies are `FALSE`: wait for natural settlement without timed retreat.
  Presets are empty and soul switching/marking are disabled, so prepare the
  current lineup manually. No saved preset is guessed from another task.
- `lock_team_enable: true` skips every pre-battle preset change, including
  changes between enemy types. It does not click the game's lock/unlock control;
  set the desired locked lineup in the game. Soul preloading remains independent.
- Normal completion returns to the courtyard and schedules the next run, rather
  than stopping the instance for human takeover. Protective failures still stop
  for inspection. Stop supervised test instances manually after reviewing them.

## Production deployment

Back up production code and private configs, then stop the affected instances
and backend before updating the checkout. Preserve each production account's
device settings, current global skin selection, scheduler and unrelated tasks;
do not copy an entire old trial config over production. Configure `process_manage`
and `abyss_shadows_time` using the current model/examples, remove obsolete trial
options, and review the resulting GUI schema before restarting. Publishing `prod`
does not authorize starting services or enabling any account's task.

## Four-account settings

[abyss-trial-accounts.json](../../deploy/examples/abyss-trial-accounts.json) contains
sanitized **process_manage patches**, not complete runnable account configurations.
Apply only the matching task subsection to a stopped, isolated trial instance;
preserve its device, global settings, scheduler, and saved progress. Never replace
an entire private configuration with this file. Preparing these patches does not
deploy them to the production host.

| Accounts | Primary targets | Backup targets | Presets (all enemy types) |
|---|---|---|---|
| 1 / 2 | All A, then all B | D boss, C boss, both D generals, both C generals, all D elites, all C elites | 7,2 / 7,1 |
| 3 / 4 | All C, then all D | B boss, A boss, both B generals, both A generals, all B elites, all A elites | 6,1 / 2,1 |

Primary regions still expand elites → generals → boss. Backup targets use explicit
`A-1` notation; no new parser or automatic coordination is needed. All four
patches enable locked-lineup mode and soul preloading, disable marking, and use
`FALSE` battle strategies. Equal soul presets are preloaded only once per task
startup, not per region or battle. Lock mode does not disable this preload.

## Page transitions and latency

- The first three difficulty menu rows use separate search regions: Easy
  `(620,380,90,64)`, Normal `(620,450,90,64)`, Hard `(620,520,90,64)`.
  They exclude the current-difficulty display below the dropdown. Existing
  templates/thresholds are unchanged; Extreme is not supported. The supplied
  recording shows Hard locked, so unlocked Hard selection is not live-verified.
  Small UI-only open/closed menu crops are bundled as regression fixtures;
  these do not contain account names, chat, or complete screenshots.
- Reuse the account's global `costume_config`: battle and records templates are
  replaced by `CostumeBase` during task initialization. No Abyss-specific skin
  selector or duplicated skin assets are added. Offline tests apply the same mapping.
- Exit records only while its page marker is visible. Stop once both the
  Abyss navigation and shikigami-entry icons appear and records is gone. A yellow
  back button on its own never authorizes another back click. Unknown transitions
  wait and request takeover after 30 seconds.
- Challenge entry accepts an already running battle, not just a preparation
  page. Preparation/preset panels take precedence over the exit icon; battle
  confirmation requires the globally themed battle-info marker.
  A visible, enabled preparation button is retried; a dark button or an open
  preset panel is not clicked. An exit icon alone does not prove battle entry.
- With lock mode off, select the configured preset when needed, then inspect a
  fresh frame before attempting preparation. With lock mode on, never select
  a preset in battle preparation. An already running battle is never interrupted
  to change lineups, regardless of lock mode.
- Explicit click/swipe retry intervals are doubled within this task, including
  shared components called by it: 0.6→1.2s, 1→2s, 2→4s. Shared component source,
  screenshots, battle deadlines, action durations, fixed sleeps, and scheduler
  intervals are not changed. Calls without a retry interval retain their contract.
- Entry/records-exit state changes are logged. Protective entry, records-exit,
  battle, or battle-exit timeouts preserve a diagnostic frame under
  `log/error/abyss/`. Treat these frames as private; do not publish raw captures.

## Behavior and limits

`TRUE` means immediate retreat, 1–3 digits mean seconds, and 4+ digits mean a
damage threshold (inclusive). `FALSE` waits for natural settlement. These are
legacy refactor semantics, not the proposed future unlimited clear-area mode.
Each target still has at most two attempts. Failed navigation and exhausted
attempts go to `saved_params.failed`, not `done`, and do not count toward optional
2/4/6 completion quotas. An unconfirmed return to the map is not victory.

Battle waiting is bounded at 300 seconds; exceeding it requests human takeover
without deliberately surrendering. Exit confirmation is bounded at 30 seconds,
and screenshot frequency is restored on exceptions. Preparation/attack-phase
confirmation failures also stop for inspection. The upstream fix for resuming
an active map through Shenshe is retained.

There is no two-hour startup cutoff. The task uses its scheduler settings for
the next run; the upstream version's
separate Friday/Saturday/Sunday time fields are not part of this schema.
The old `general_battle_config` and `switch_soul_config` groups are replaced by
`process_manage`; do not expect upstream configurations to carry over implicitly.

Progress is scoped to the calendar date. Normal completion clears it if no
failed targets remain; otherwise it is retained and the failure schedule is used.
Completion schedules relative to finishing time with the success/failure interval.
The shared scheduler treats `server_update=09:00` as no forced clock time; other
values replace the interval result with `server_update`/`delay_date`, and
`float_time` adds random delay. Failed region entry uses the failure interval
relative to task start without the server-time override. Non-Friday/Saturday/Sunday
runs exit using the success schedule without entering the activity.
Before a deliberate fresh replay, clear `saved_params` only while stopped.
Progress writes reload configuration before saving unrelated fields; concurrent
editing of a running task remains unsupported.

Recorded-frame tests cover records/map/preparation/battle discrimination across
the four supplied accounts, including the alternate interface skin. This is
offline evidence, not live validation of the restored normal scheduling path. Region-sealed OCR and
individual enemy-death classification still require separate verification.
This trial does not add reliable per-enemy death recognition, unlimited retries,
or automatic four-account group coordination. Multiple preset soul loadouts are
preloaded in deterministic order; shared shikigami may still overwrite each
other's loadouts. Leave switching disabled until the teams have been reviewed.

Capture from before entry until returning to the courtyard. Keep recordings,
private configs and logs locally. Stop the trial instance before manual control;
closing a GUI window alone may leave a backend clicking. Stop the test backend
afterward, then resume the production instance on that emulator.

## Validation

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

Checks cover real OCR pixel filtering and mocked Abyss control flow. They do not
consume an activity opportunity. To also run the private 44-frame regression,
set `ABYSS_RECORDING_FRAMES` to the extracted-frame directory; the test skips
when it is absent. Raw frames/recordings are not bundled or uploaded. Regenerate
`assets.py` with `AssetsExtractor('tasks/AbyssShadows').extract()` from
`dev_tools.assets_extract` after editing source JSON/images.
