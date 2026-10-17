# Hero Test

[简体中文](README.zh.md)

The configured mode selects Ghost Army Exercise, Weapon Storage Secret Realm,
Inheritance Trial, or Dream Secret Realm. Entry and return navigation use the
current task's page copies. Dynamic mode connections do not change global pages
or another instance's selected mode.

Soul presets, team locking, tickets, skill selection, battle limits and scheduling
retain their existing behavior. The distinct Start Challenge text is searched in
`(640,345,235,200)` so small dialog shifts do not hide the button. Entry handles
Start Challenge and Confirm Reset before the retry limit, allows two seconds
after each click for a transition, and has a 30-second total deadline. Three or
four challenge clicks remain the limit. A genuine entry failure raises
`GameStuckError` for existing recovery without scheduling the task for next week;
insufficient tickets retain the normal skip behavior.

Navigation and entry checks run without a device or game:

```sh
python -m pytest tests/test_hero_test_navigation.py tests/test_hero_test_skill_fallback.py tests/test_hero_test_entry.py
```
