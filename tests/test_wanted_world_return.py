"""A confirmed world return must let the caller reread real wanted progress."""
import unittest
from types import SimpleNamespace

from tasks.Component.Costume.config import MainType
from tasks.Exploration.base import Scene
from tasks.WantedQuests.explore import WQExplore


class OfflineWantedExplore:
    I_UI_BACK_YELLOW = 'back'
    I_E_EXPLORATION_CLICK = 'chapter'
    I_CHECK_EXPLORATION = 'world'

    def __init__(self, scenes):
        self.scenes = iter(scenes)
        self.seen = []
        self.stability_checks = 0
        self.config = SimpleNamespace(model=SimpleNamespace(global_game=SimpleNamespace(
            costume_config=SimpleNamespace(costume_main_type=MainType.COSTUME_MAIN))))
        self.TEMPLATE_GIF = SimpleNamespace(match_origin=lambda: None)

    def screenshot(self):
        pass

    def appear(self, rule):
        return rule in ('back', 'chapter')

    def appear_then_click(self, *args, **kwargs):
        raise AssertionError('Already at the entrance; no destination click is needed')

    def get_current_scene(self, **kwargs):
        try:
            scene = next(self.scenes)
        except StopIteration:
            raise AssertionError('World return kept looping instead of refreshing wanted progress')
        self.seen.append(scene)
        return scene

    def wait_until_stable(self, *args, **kwargs):
        self.stability_checks += 1


class WantedWorldReturnTests(unittest.TestCase):
    def test_world_before_local_quota_returns_without_claiming_more_battles(self):
        task = OfflineWantedExplore([Scene.WORLD, Scene.WORLD])
        WQExplore.explore(task, goto='wanted destination', num=3)
        self.assertEqual(task.seen, [Scene.WORLD, Scene.WORLD])
        self.assertEqual(task.stability_checks, 1)

    def test_transient_world_requires_a_second_confirmed_world_pair(self):
        scenes = [Scene.WORLD, Scene.UNKNOWN, Scene.WORLD, Scene.WORLD]
        task = OfflineWantedExplore(scenes)
        WQExplore.explore(task, goto='wanted destination', num=3)
        self.assertEqual(task.seen, scenes)
        self.assertEqual(task.stability_checks, 2)
