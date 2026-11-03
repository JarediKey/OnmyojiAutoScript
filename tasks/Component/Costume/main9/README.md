# Shrine of Bonds courtyard

[简体中文](README.zh.md)

The Exploration entry uses a complete two-character label with a 0.8 template
threshold. It searches `(234, 95, 904, 100)` on the 1280×720 screen, allowing the
courtyard's horizontal position to vary. A match supplies the click position;
there is no fixed-coordinate fallback when recognition fails.

Edit `image.json` and the cropped label image, then regenerate the parent
`assets.py` with `dev_tools/assets_extract.py`. Validate both the returned click
position and recognition against real courtyard frames before deployment.
