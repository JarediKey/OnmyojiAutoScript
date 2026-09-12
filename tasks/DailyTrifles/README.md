# DailyTrifles

[简体中文](README.zh.md)

After shop actions, the task identifies its current page and navigates to the courtyard. It does not require an intermediate shop page after pressing back, because the game may already have returned to the courtyard. Purchase and sign-in settings are unchanged.

Recovery checks: `python -m unittest discover -s tests -p test_login_and_secret_recovery.py -v`. Offline checks do not replace live game validation.
