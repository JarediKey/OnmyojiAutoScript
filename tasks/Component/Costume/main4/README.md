# Main4 courtyard navigation

[简体中文](README.zh.md)

Town matching uses the two label characters without the surrounding animated
fabric. Exploration uses the current lantern text. Both retain a 0.8 threshold
and their original horizontal search bands. Input follows a successful match;
these rules do not click an unrecognized fixed position.

`tests/test_runtime_ui_blockers.py` replays cropped incident UI and checks unrelated
pages as negatives. This does not verify every animation or live game transition.
