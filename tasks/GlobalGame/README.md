# Shared dialogs

[简体中文](README.zh.md)

Tasks use `BaseTask.I_UI_CONFIRM_DIALOG` for an expected plain “确定” or “确认”
dialog. The matcher reuses complete long, compact, plain and blue button images
from GlobalGame, searches `(350,300,600,400)` on the 1280×720 screen, and clicks
inside the button that actually matched. All variants share one cooldown identity.
Task-owned duplicates are removed; task-specific actions and completion checks stay
with their callers. The broader matcher is not an unknown-page closer.

Buttons with other meanings or text, including Create, Invite, Start, Confirm Reset,
and skill-selection page markers, retain their own recognition. HeroTest's Confirm
Reset image and search region follow the current dialog. These buttons are not
interchangeable with plain confirmation.

An explicitly recognized server-disconnection message raises `GameStuckError`
from the screenshot path, letting the existing scheduler restart the game. It
does not click an unclassified dialog. Soul-capacity notices use the existing
shared “知道了” rule during battle settlement and shop collection.

Run `python -m pytest tests/test_shared_confirmations.py`. Pixel fixtures and
incident-frame replays are offline checks; they do not verify every live game mode.
