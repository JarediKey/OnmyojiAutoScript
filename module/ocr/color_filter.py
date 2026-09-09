"""Parse OCR preprocessing methods and mask RGB screenshots without changing them."""

import re
from enum import Enum

import cv2
import numpy as np


class OcrMethod(Enum):
    DEFAULT = 1
    CF_RGB = 2
    CF_HSV = 3


ColorBounds = tuple[tuple[int, int, int], tuple[int, int, int]]
_FILTER_PATTERN = re.compile(
    r"(CF_RGB|CF_HSV)\s*\(\s*([0-9a-f]{6})\s*,\s*([0-9a-f]{6})\s*\)",
    re.IGNORECASE,
)


def parse_ocr_method(method: str | OcrMethod) -> tuple[OcrMethod, ColorBounds | None]:
    """Accept Default or CF_RGB/CF_HSV with two inclusive hexadecimal bounds."""
    if method is OcrMethod.DEFAULT:
        return OcrMethod.DEFAULT, None
    if not isinstance(method, str):
        raise ValueError("OCR method must be Default or CF_RGB/CF_HSV(lower,upper)")
    method = method.strip()
    if method.upper() == "DEFAULT":
        return OcrMethod.DEFAULT, None
    match = _FILTER_PATTERN.fullmatch(method)
    if match is None:
        raise ValueError(f"Invalid OCR method: {method!r}; expected CF_RGB/CF_HSV with two six-digit hex bounds")
    kind = OcrMethod[match.group(1).upper()]
    lower, upper = (tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
                    for value in match.group(2, 3))
    if any(low > high for low, high in zip(lower, upper)):
        raise ValueError("OCR color filter lower bounds must not exceed upper bounds")
    if kind is OcrMethod.CF_HSV and upper[0] > 179:
        raise ValueError("OCR HSV hue must be in 0..179 (00..B3 hex)")
    return kind, (lower, upper)


def apply_color_filter(image: np.ndarray, method: OcrMethod,
                       bounds: ColorBounds | None) -> np.ndarray:
    """Preserve selected RGB pixels, blacken others, and never mutate the input."""
    if method is OcrMethod.DEFAULT:
        return image
    if bounds is None:
        raise ValueError("OCR color filter requires lower and upper bounds")
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("OCR color filters require a uint8 RGB image")
    if method is OcrMethod.CF_HSV:
        colors = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    elif method is OcrMethod.CF_RGB:
        colors = image
    else:
        raise ValueError(f"Unsupported OCR color filter: {method!r}")
    lower, upper = (np.array(bound, dtype=np.uint8) for bound in bounds)
    mask = cv2.inRange(colors, lower, upper)
    return cv2.bitwise_and(image, image, mask=mask)
