# Abyss Shadows refactor trial

[简体中文](README.zh.md)

This branch is based on Jared's `prod` and includes its guild-raid fix, the OCR
color filters, and the archived Abyss refactor. Only Abyss source/assets were
ported from the archive. Neither the published `prod` branch nor production
instance files need to change for this trial.

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
- `trial_mode: true` stops with a human-takeover message after the run and keeps
  target progress for inspection. The backend may display the instance as
  warning; this is intentional and does not indicate that every target died.

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

The old two-hour startup cutoff has been removed. Outside trial mode, the
refactor uses its scheduler settings for the next run; the upstream version's
separate Friday/Saturday/Sunday time fields are not part of this schema.
The old `general_battle_config` and `switch_soul_config` groups are replaced by
`process_manage`; do not expect upstream configurations to carry over implicitly.

Progress is scoped to the calendar date and is preserved at trial completion.
Before a fresh replay, clear the four `saved_params` fields while the instance
is stopped. Progress writes reload configuration before saving unrelated fields.
Concurrent editing of the running trial is still unsupported.

Region-sealed OCR and imported images remain unverified against today's UI.
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
consume an activity opportunity or verify current game screenshots. Regenerate
`assets.py` with `AssetsExtractor('tasks/AbyssShadows').extract()` from
`dev_tools.assets_extract` after editing source JSON/images.
