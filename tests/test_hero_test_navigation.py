"""Verify dynamic HeroTest navigation on real task-local page snapshots."""

import unittest
from types import SimpleNamespace

from tasks.GameUi.page import page_hero_test
from tasks.GameUi.registry import PageRegistry
from tasks.GameUi.session import NavigatorSession
from tasks.HeroTest.config import Layer
from tasks.HeroTest.script_task import ScriptTask


class HeroNavigationTests(unittest.TestCase):
    def make_task(self, layer):
        task = object.__new__(ScriptTask)
        task.conf = SimpleNamespace(herotest=SimpleNamespace(layer=layer))
        task.navigator = NavigatorSession(task_category='HeroTest')
        task.navigator.bootstrap(PageRegistry.all())
        return task

    def test_each_mode_has_entry_and_return_routes(self):
        actions = {
            Layer.YANWU: ScriptTask.I_GBB,
            Layer.MIJING: ScriptTask.I_BCMJ,
            Layer.CHUANCHENG: ScriptTask.I_ENTER_CCSL,
            Layer.MENGXU: ScriptTask.I_ENTER_MXMJ,
        }
        for layer, action in actions.items():
            with self.subTest(layer=layer):
                task = self.make_task(layer)
                task.init_pages()
                home = task.navigator.resolve_page(page_hero_test)
                path = task._build_path(home, task.page_hero_mode)
                self.assertEqual(len(path), 1)
                self.assertIs(path[0].action, action)
                back = task._build_path(task.page_hero_mode, home)
                self.assertEqual(len(back), 1)
                self.assertIs(back[0].destination, home)

    def test_dynamic_connections_do_not_modify_global_pages(self):
        before = list(page_hero_test.transitions)
        task = self.make_task(Layer.MENGXU)
        task.init_pages()
        self.assertEqual(page_hero_test.transitions, before)

    def test_instances_keep_independent_mode_connections(self):
        first = self.make_task(Layer.MENGXU)
        second = self.make_task(Layer.YANWU)
        first.init_pages()
        second.init_pages()
        for task, action in ((first, first.I_ENTER_MXMJ), (second, second.I_GBB)):
            home = task.navigator.resolve_page(page_hero_test)
            self.assertIs(task._build_path(home, task.page_hero_mode)[0].action, action)


if __name__ == '__main__':
    unittest.main()
