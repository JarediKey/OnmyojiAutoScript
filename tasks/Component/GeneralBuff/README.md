# Buff controls

[简体中文](README.zh.md)

The 1280×720 buff panel places round switches in column x=844–904. OCR or the
buff icon selects the row; text width does not determine the switch position.
Full round-control templates distinguish active and paused states at threshold
0.9. Clicks use the center of the matched control, not the timer or colored strip.

Gold, experience, awakening and soul buffs share state confirmation. If the
requested state is already visible, no click occurs. Otherwise, at most three
clicks are made two seconds apart, followed by fresh screenshots within a
10-second deadline. Unknown states are not clicked. Failure returns false and
retains the caller's existing warning/exit behavior.

Checks: `python -m pytest tests/test_buff_switch_control.py`. Real incident images
remain private on Ebony; offline replay does not toggle game buffs.
