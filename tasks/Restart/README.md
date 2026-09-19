# Restart

[简体中文](README.zh.md)

Each login attempt allows up to 30 actual clicks on Enter Game. The two OCR
variants share this counter; a requested 31st click raises the repeated-click
error and follows the existing login retry flow. Only these clicks bypass the
generic repeated-click guard. Other buttons keep their existing protection.
The 3-second OCR interval, up-to-5-second post-click wait, and two login attempts
remain unchanged.

Mail collection uses the fixed courtyard toolbar envelope first, then the moving courier if necessary. Mail entry has a 12-second deadline and is attempted once per harvest pass. If entry fails, login continues and mail is deferred until the next login. Reward collection options remain unchanged.

Login and recovery checks: `python -m unittest discover -s tests -p 'test_login*py' -v`. Offline checks do not replace live game validation.
