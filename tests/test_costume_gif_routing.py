"""Verify courtyard GIF matching preserves references held by page routing."""
from types import SimpleNamespace
from unittest.mock import Mock

from module.atom.image import RuleImage
from tasks.Component.Costume import costume_base as costume
from tasks.Component.Costume.config import MainType
from tasks.WeeklyTrifles.config import Trifles


def rule(name, front):
    return RuleImage(roi_front=front, roi_back=(180, 100, 240, 180),
                     threshold=0.8, method='Template matching', file=name+'.png')


def test_courtyard_multiframe_matching_keeps_page_reference(monkeypatch):
    original = rule('original', (0, 0, 1, 1))
    routing = SimpleNamespace(check=original)
    owner = costume.CostumeBase()
    owner.I_CHECK_MAIN = original
    frames = [rule(f'frame{i}', (200+i, 168, 80, 54)) for i in range(3)]
    for i, frame in enumerate(frames):
        frame.match = Mock(return_value=i == 2)
    assets = SimpleNamespace(**dict(zip(
        ('I_CHECK_MAIN_17_A', 'I_CHECK_MAIN_17_B', 'I_CHECK_MAIN_17_C'), frames)))
    monkeypatch.setattr(costume, 'CostumeAssets', lambda: assets)
    owner.check_costume_main(MainType.COSTUME_MAIN_17)
    assert owner.I_CHECK_MAIN is routing.check is original
    screenshot = object()
    assert routing.check.match(screenshot)
    assert routing.check.roi_front == frames[2].roi_front
    assert routing.check.front_center() == frames[2].front_center()
    for frame in frames:
        frame.match.assert_called_once_with(screenshot, 0.8)


def test_missing_optional_skin_assets_are_skipped(monkeypatch):
    owner = costume.CostumeBase()
    monkeypatch.setattr(costume, 'CostumeAssets', lambda: SimpleNamespace())
    owner.check_costume_main(MainType.COSTUME_MAIN_17)


def test_touch_fish_is_disabled_by_default():
    assert Trifles().save_touch_fish is False
