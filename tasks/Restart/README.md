# Restart

[简体中文](README.zh.md)

Mail collection uses the fixed courtyard toolbar envelope first, then the moving courier if necessary. Mail entry has a 12-second deadline and is attempted once per harvest pass. If entry fails, login continues and mail is deferred until the next login. Reward collection options remain unchanged.

Recovery checks: `python -m unittest discover -s tests -p test_login_and_secret_recovery.py -v`. Offline checks do not replace live game validation.
