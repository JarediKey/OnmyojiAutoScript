# Skin matching

[简体中文](MATCHING.zh.md)

Replacing a skin updates the existing image rule so navigation references remain
valid. Pixel and feature caches are cleared and the replacement matching method
is applied. A previously loaded template must not survive a skin change. Rules
with a fixed search area keep that area when `rp_roi_back=False`.

Regression check: `python -m pytest tests/test_skin_template_reload.py`.
