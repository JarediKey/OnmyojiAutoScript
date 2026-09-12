# WantedQuests

[简体中文](README.zh.md)

After each secret-zone battle, recognized story dialogue is advanced before returning to navigation. Only the story nameplate triggers clicks. The story handler waits for stable disappearance and has a 30-second deadline; unresolved dialogue raises GameStuckError. Other battles and unrecognized pages are not clicked by this handler.

Recovery checks: `python -m unittest discover -s tests -p test_login_and_secret_recovery.py -v`. Offline checks do not replace live game validation.
