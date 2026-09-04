# OCR color filtering

[简体中文](README.zh.md)

OCR rules accept these `method` strings in source JSON and `RuleOcr`:

| Method | Behavior |
|---|---|
| `Default` | Existing preprocessing behavior: pass the image through unchanged. |
| `CF_RGB(CCCCCC,FFFFFF)` | Keep pixels with every RGB channel between 204 and 255, inclusive. |
| `CF_HSV(0980B4,1ED2FF)` | Keep pixels whose HSV values are H=9..30, S=128..210, V=180..255. |

Each bound consists of three hexadecimal bytes. Method names and hex digits are
case-insensitive; surrounding whitespace is allowed. Bounds are inclusive and
must be ordered per channel. For uint8 OpenCV HSV, H is 0..179 (`00`..`B3`), and
S/V are 0..255. Hue wraparound ranges are not supported. Malformed methods raise
`ValueError` at rule construction rather than silently disabling filtering.

Color filters require a uint8, three-channel **RGB** image. They blacken rejected
pixels and preserve accepted pixels' original RGB values, dimensions and dtype
without changing the source screenshot. HSV selection does not round-trip the
accepted RGB pixels through HSV. `Default` and `OcrMethod.DEFAULT` continue to
work, including the import from `module.ocr.base_ocr`.

Filtering runs in `BaseCor.pre_process`, before both single-line and detection
inference, whether the model is local or reached through the existing OCR proxy.
The OCR service protocol, postprocessing and coordinate handling are unchanged.
Task-specific `pre_process` overrides remain authoritative; they can call
`super().pre_process(image)` if they also want the configured color filter.

Edit the source OCR JSON and regenerate `assets.py` with
`dev_tools/assets_extract.py`; do not hand-edit generated asset declarations.
The browser annotator's text `method` field accepts these expressions directly.
The older QML rule editor only offers `Default`; it has not gained a color-range
editor. Keep custom methods in source JSON when using that editor.

Run the isolated regression suite with:

```sh
python -m unittest discover -s tests -p 'test_ocr_color_filter.py' -v
```

The suite uses real NumPy/OpenCV pixels and stubs model/service loading for OCR
integration checks. It does not download model weights, connect to a device, or
prove accuracy against the current Abyss Shadows UI. Test the filters on fresh
1280x720 captures before using the legacy color bounds in production.

Reference: [OpenCV inRange tutorial](https://docs.opencv.org/4.x/da/d97/tutorial_threshold_inRange.html).
