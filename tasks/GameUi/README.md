# Page navigation

[简体中文](README.zh.md)

When navigation finds an active battle or preparation page, the battle hook uses
the current task's `GeneralBattle` implementation if available. A navigation-only
task such as GotoMain creates `GeneralBattle` with the same configuration and
device to handle the battle before continuing navigation. No missing helper import
is required. Existing task-specific battle waiting remains in use.

Regression check: `python -m pytest tests/test_navigation_battle_hook.py`.

Shared login and battle components keep the invoking task's identity. The strict
name/path check applies to task entry scripts (`script_task.py`), not shared
helpers such as LoginHandler. A task can recover from the login page without
being rejected for belonging to another task folder.
