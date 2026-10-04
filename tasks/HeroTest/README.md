# Hero Test

[简体中文](README.zh.md)

The configured mode selects Ghost Army Exercise, Weapon Storage Secret Realm,
Inheritance Trial, or Dream Secret Realm. Entry and return navigation use the
current task's page copies. Dynamic mode connections do not change global pages
or another instance's selected mode.

Soul presets, team locking, tickets, skill selection, battle limits and scheduling
retain their existing behavior. Navigation checks run without a device or game:

```sh
python -m pytest tests/test_hero_test_navigation.py tests/test_hero_test_skill_fallback.py
```
