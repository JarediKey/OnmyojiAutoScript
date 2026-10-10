# Soul preset switching

[简体中文](README.zh.md)

Numeric and named preset flows use the shared `I_UI_CONFIRM` image from
GlobalGame. Costume-specific soul confirmation templates are removed; confirmation
recognition follows the current shared button region and threshold.

Named switching locates the target row with OCR and clicks its apply button at
the vertical center of the name box, avoiding the editable name.

The component allows five seconds to locate the target, then observes the UI
for up to five seconds. A visible confirmation dialog is retried at 0.8-second
intervals. Once any dialog is observed, success requires a confirmation click
followed by at least 0.8 seconds and multiple frames with the dialog absent and
the shikigami records indicator visible. Confirmation does not require the
target name to remain visible, and click cooldown does not imply dialog closure.

When the preset is already applied, the game may omit confirmation. If no dialog
appears during the entire observation window, the component accepts this flow
after three application clicks, spaced at least 1.5 seconds apart, with the
target name and records indicator still visible and stable for at least 0.8
seconds after the final click. This is a bounded UI heuristic: the interface
provides no independent proof that the intended souls are equipped, so repeated
ignored clicks cannot be distinguished conclusively from an already applied preset.

Missing targets, failed application retries, unknown pages, and uncompleted
dialogs raise `GameStuckError` for scheduler recovery. Numeric switching is unchanged.

Run offline regression checks from the repository root:

```sh
python -m unittest discover -s tests -p test_soul_confirmation.py -v
```

These checks simulate frames and time; they are not live game validation.
