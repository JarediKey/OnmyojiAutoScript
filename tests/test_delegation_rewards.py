"""Dependency-free behavioral tests of the production reward methods."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class Takeover(Exception):
    pass


class Timer:
    now = 0

    def __init__(self, limit):
        self.limit = limit
        self.started = self.now

    def start(self):
        self.started = self.now
        return self

    reset = start

    def reached(self):
        return self.now - self.started >= self.limit


def load_task():
    path = Path(__file__).resolve().parents[1] / 'tasks/Delegation/script_task.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    cls.bases = []
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name in ('completed_card', 'check_reward')]
    ns = dict(Timer=Timer, RequestHumanTakeover=Takeover,
              RuleClick=lambda **kw: SimpleNamespace(**kw), logger=Mock())
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(path), 'exec'), ns)
    return ns['ScriptTask']


class Box:
    def __init__(self, x, y):
        self.points = [(x, y), (x + 57, y), (x + 57, y + 34)]

    def __getitem__(self, key):
        row, col = key
        return self.points[row][col]


class RewardsTests(unittest.TestCase):
    def setUp(self):
        Timer.now = 0
        self.task = load_task()()
        self.task.device = SimpleNamespace(image=None)
        for name in ('GET', 'CHAT', 'DONE', 'FALSE', 'MIN'):
            setattr(self.task, 'I_REWARDS_' + name, name)
        self.task.I_CHAT_1, self.task.I_CHAT_2 = 'CHAT1', 'CHAT2'
        self.task.screenshot = lambda: setattr(Timer, 'now', Timer.now + 0.5)
        self.task.appear_then_click = Mock(return_value=False)
        self.task.appear = Mock(return_value=True)
        self.task.click = Mock(side_effect=lambda *a, **k: Timer.now % 3 == 0)

    def rule(self, boxes):
        self.task.O_D_DONE = SimpleNamespace(
            roi=(675, 129, 441, 517), keyword='完成',
            detect_and_ocr=lambda image: [SimpleNamespace(box=b) for b in boxes],
            filter=lambda results, keyword: list(range(len(results))))

    def test_incident_click_is_below_ribbon(self):
        self.rule([Box(321, 134)])
        card = self.task.completed_card()
        self.assertEqual(card.roi_front, (1016, 314, 16, 16))

    def test_multiple_matches_select_topmost_not_midpoint(self):
        self.rule([Box(321, 388), Box(321, 134)])
        self.assertEqual(self.task.completed_card().roi_front, (1016, 314, 16, 16))

    def test_no_completed_tasks_returns_normally(self):
        self.rule([])
        self.task.check_reward()
        self.task.click.assert_not_called()

    def test_unresponsive_card_requests_takeover(self):
        self.rule([Box(321, 134)])
        with self.assertRaisesRegex(Takeover, 'after 3 clicks'):
            self.task.check_reward()
        self.assertEqual(self.task.click.call_count, 3)
        self.assertLess(Timer.now, 20)

    def test_unknown_screen_times_out(self):
        self.task.appear.return_value = False
        with self.assertRaisesRegex(Takeover, '20 seconds'):
            self.task.check_reward()

    def test_ribbon_disappearance_does_not_prove_success(self):
        self.task.completed_card = lambda: object() if Timer.now <= 3 else None
        with self.assertRaisesRegex(Takeover, '20 seconds'):
            self.task.check_reward()

    def test_reward_action_allows_normal_completion(self):
        self.task.completed_card = lambda: object() if Timer.now <= 3 else None
        self.task.appear_then_click.side_effect = lambda rule, **kw: Timer.now == 3.5 and rule == 'GET'
        self.task.check_reward()
        self.assertGreaterEqual(Timer.now, 6.5)
        self.assertLess(Timer.now, 20)


if __name__ == '__main__':
    unittest.main()
