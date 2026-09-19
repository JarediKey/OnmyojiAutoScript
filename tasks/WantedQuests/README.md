# WantedQuests

[简体中文](README.zh.md)

After each secret-zone battle, recognized story dialogue is advanced before returning to navigation. The existing story landmark and a Shantu nameplate template trigger clicks at a 1.5-second interval. A visible story takes precedence over destination markers. Completion requires the challenge button or secret-zone list to remain visible for at least one second across multiple screenshots. A missing story match alone never means completion.

Unknown frames are not clicked and reset destination confirmation. The handler has a 30-second deadline; failure to confirm a destination raises `GameStuckError` for the existing recovery flow. Waiting for the next challenge is bounded to 10 seconds, and returning to the secret-zone list after the battles is bounded to 20 seconds. These checks do not mark an incomplete task as successful.

The new template was checked against three captured Shantu incident frames and a courtyard negative sample. Regression fixtures contain only cropped UI regions. Other unrecognized dialogue pages still require additional evidence/templates; live game replay has not been performed.

Recovery checks: `python -m unittest discover -s tests -p test_login_and_secret_recovery.py -v`. Template checks: `python -m unittest discover -s tests -p test_wanted_story_assets.py -v` (requires OpenCV). Offline checks do not replace live game validation.
