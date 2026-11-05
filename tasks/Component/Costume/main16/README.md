# Fox courtyard navigation

[简体中文](README.zh.md)

The Town entry uses the current complete label crop, with a 0.8 matching
threshold and search region `(950, 295, 125, 125)` on a 1280×720 frame.
The label supplies the click position; a failed match does not click a fixed point.
Edit `image.json` and the image, then regenerate the parent `assets.py` through
`dev_tools/assets_extract.py`. Validate against current courtyard frames.
