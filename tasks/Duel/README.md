# Duel preparation

[简体中文](README.zh.md)

The entry gift's “开心收下” button is handled before reading the score or clicking
the battle button. It reuses WeeklyTrifles' acknowledgement bitmap with a Duel
search region. Matching takes a fresh screenshot after every click and checks
the popup again, including while its click cooldown is active. A visible battle
button behind the popup cannot cause repeated start clicks.

Upstream PR #1971 handles high-rank ban selection and lineup confirmation.
The ban page recognizes the already-banned stamp and stops clicking when it is
visible. Each match permits at most five ban clicks. Forty ban-page loops without
progress request the existing battle-exit flow. A valid, unbanned lineup clicks
the confirmation region `(1120,560,120,85)` before waiting for battle.

The stamp and confirmation regions are defined in source JSON and regenerated
through `dev_tools/assets_extract.py`. Offline checks are in
`tests/tasks/Duel/test_duel_ban_already.py`. They cover template separation and
bounded input; they do not verify every current live duel stage.
