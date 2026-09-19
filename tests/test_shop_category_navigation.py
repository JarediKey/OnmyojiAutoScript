"""Check ordered sidebar navigation with simulated UI and captured sidebar pixels."""
import ast
from pathlib import Path
import json
import runpy
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
Timer = runpy.run_path(str(ROOT / 'module/base/timer.py'))['Timer']
GameStuckError = runpy.run_path(str(ROOT / 'module/exception.py'))['GameStuckError']
ORDER = ('special', 'duel', 'friendship', 'medal', 'charisma')
ATTRS = ('I_SIDE_SURE_SPECIAL', 'I_SIDE_SUER_HONOR', 'I_SIDE_SURE_FRIENDS',
         'I_SIDE_SURE_MEDAL', 'I_SIDE_SURE_CHARISMA')


def bind(task, namespace):
    tree = ast.parse((ROOT / 'tasks/RichMan/mall/navbar.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    names = {'_sundry_categories', '_read_sundry_sidebar', '_enter_sundry_category',
             '_enter_special', '_enter_honor', '_enter_friendship', '_enter_medal', '_enter_charisma'}
    body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=body, type_ignores=[]), '<sidebar>', 'exec'), namespace)
    for name in names:
        setattr(task, name, MethodType(namespace[name], task))


class SidebarNavigationTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        p = patch('time.time', side_effect=lambda: self.now)
        p.start(); self.addCleanup(p.stop)
        self.task = SimpleNamespace(_enter_sundry=Mock(), click=Mock(), swipe=Mock(return_value=None),
                                    S_MALL_CATEGORIES_EARLIER='earlier', S_MALL_CATEGORIES_LATER='later')
        self.buttons = {name: SimpleNamespace(name=name) for name in ORDER}
        for name, attr in zip(ORDER, ATTRS): setattr(self.task, attr, self.buttons[name])
        self.task.screenshot = Mock(side_effect=lambda: self.advance(.25))
        bind(self.task, dict(Timer=Timer, GameStuckError=GameStuckError, logger=Mock(),
                             time=SimpleNamespace(sleep=self.advance)))

    def advance(self, seconds): self.now += seconds

    def observe(self, visible, selected):
        return {name: self.buttons[name] for name in visible}, selected

    def test_all_five_wrappers_use_the_requested_order(self):
        self.assertEqual(tuple(name for name, _ in self.task._sundry_categories()), ORDER)
        self.task._enter_sundry_category = Mock()
        for method, target in zip(('_enter_special', '_enter_honor', '_enter_friendship', '_enter_medal', '_enter_charisma'), ORDER):
            getattr(self.task, method)()
            self.task._enter_sundry_category.assert_called_with(target)

    def test_selected_target_needs_no_click_or_scroll(self):
        self.task._read_sundry_sidebar = lambda: self.observe(('medal', 'charisma'), 'medal')
        self.task._enter_medal()
        self.task.click.assert_not_called(); self.task.swipe.assert_not_called()
        self.assertGreater(self.now, 101)

    def test_visible_target_is_clicked_without_scrolling(self):
        self.task._read_sundry_sidebar = lambda: self.observe(ORDER, 'medal' if self.task.click.called else 'duel')
        self.task._enter_medal()
        self.task.click.assert_called_once_with(self.buttons['medal'])
        self.task.swipe.assert_not_called()

    def test_lower_target_uses_finger_upward(self):
        def observe():
            if not self.task.swipe.called: return self.observe(ORDER[:3], 'duel')
            return self.observe(ORDER[2:], 'charisma' if self.task.click.called else None)
        self.task._read_sundry_sidebar = observe
        self.task._enter_charisma()
        self.task.swipe.assert_called_once_with('later')
        self.task.click.assert_called_once_with(self.buttons['charisma'])

    def test_earlier_target_uses_finger_downward(self):
        def observe():
            if not self.task.swipe.called: return self.observe(ORDER[3:], 'charisma')
            return self.observe(ORDER[:3], 'special' if self.task.click.called else None)
        self.task._read_sundry_sidebar = observe
        self.task._enter_special()
        self.task.swipe.assert_called_once_with('earlier')
        self.task.click.assert_called_once_with(self.buttons['special'])

    def test_no_labels_does_not_guess_a_direction(self):
        self.task._read_sundry_sidebar = lambda: ({}, None)
        with self.assertRaisesRegex(GameStuckError, '25 seconds'): self.task._enter_medal()
        self.task.swipe.assert_not_called(); self.task.click.assert_not_called()
        self.assertLessEqual(self.now, 126)

    def test_missing_target_between_visible_labels_does_not_scroll_blindly(self):
        self.task._read_sundry_sidebar = lambda: self.observe(('special', 'friendship'), 'special')
        with self.assertRaisesRegex(GameStuckError, '25 seconds'): self.task._enter_honor()
        self.task.swipe.assert_not_called()

    def test_swipe_count_is_bounded_even_when_swipe_returns_none(self):
        self.task._read_sundry_sidebar = lambda: self.observe(ORDER[:3], 'duel')
        with self.assertRaisesRegex(GameStuckError, '3 sidebar swipes'): self.task._enter_medal()
        self.assertEqual(self.task.swipe.call_count, 3)
        self.task.click.assert_not_called()

    def test_clicks_need_selection_confirmation_and_have_a_limit(self):
        times = []
        self.task.click.side_effect = lambda button: times.append(self.now)
        self.task._read_sundry_sidebar = lambda: self.observe(ORDER, 'duel')
        with self.assertRaisesRegex(GameStuckError, '3 clicks'): self.task._enter_medal()
        self.assertEqual(len(times), 3)
        self.assertTrue(all(b-a >= 3 for a,b in zip(times,times[1:])))
        self.task.swipe.assert_not_called()

    def test_transient_highlight_does_not_finish_early(self):
        def observe():
            selected = 'medal' if self.now in (100.5, 100.75) or self.now >= 105 else None
            return self.observe(ORDER, selected)
        self.task._read_sundry_sidebar = observe
        self.task._enter_medal()
        self.assertGreaterEqual(self.now, 106)


class SidebarImageTests(unittest.TestCase):
    def setUp(self):
        rules = json.loads((ROOT / 'tasks/RichMan/mall/navbar/image_side.json').read_text(encoding='utf-8'))
        self.rules = {r['itemName']: r for r in rules}
        self.task = SimpleNamespace()
        for attr in (*ATTRS, 'I_MALL_CATEGORY_SELECTED'):
            r = self.rules[attr[2:].lower()]
            marker = SimpleNamespace(name=attr, roi_front=list(map(int,r['roiFront'].split(','))),
                roi_back=tuple(map(int,r['roiBack'].split(','))), threshold=r['threshold'],
                image=cv2.imread(str(ROOT / 'tasks/RichMan/mall/navbar' / r['imageName'])))
            setattr(self.task, attr, marker)
        self.frame = np.zeros((720,1280,3),dtype=np.uint8)
        self.frame[90:610,1156:1268] = cv2.imread(str(ROOT/'tests/fixtures/shop_sidebar/duel_selected.png'))
        def appear(marker):
            x,y,w,h=marker.roi_back
            score=cv2.minMaxLoc(cv2.matchTemplate(self.frame[y:y+h,x:x+w],marker.image,cv2.TM_CCOEFF_NORMED))
            if score[1] <= marker.threshold: return False
            marker.roi_front[:2]=[x+score[3][0],y+score[3][1]]
            return True
        self.task.appear=appear
        bind(self.task, {})

    def test_actual_capture_identifies_duel_and_visible_primary_categories(self):
        visible,selected=self.task._read_sundry_sidebar()
        self.assertEqual(tuple(visible), ('special','duel','friendship'))
        self.assertEqual(selected,'duel')

    def test_scrolled_capture_is_recognized_without_fixed_tab_positions(self):
        self.frame[90:520,1156:1268]=self.frame[180:610,1156:1268].copy()
        self.frame[520:610,1156:1268]=0
        visible,selected=self.task._read_sundry_sidebar()
        self.assertNotIn('special',visible)
        self.assertIn('duel',visible); self.assertEqual(selected,'duel')

    def test_no_highlight_does_not_infer_selection_from_visible_labels(self):
        self.frame[190:270,1156:1186]=0
        visible,selected=self.task._read_sundry_sidebar()
        self.assertTrue(visible); self.assertIsNone(selected)

    def test_directional_swipes_stay_in_sidebar(self):
        rules=json.loads((ROOT/'tasks/RichMan/mall/navbar/swipe.json').read_text())
        for r in rules:
            start=tuple(map(int,r['roiFront'].split(',')));end=tuple(map(int,r['roiBack'].split(',')))
            for x,y,w,h in (start,end):
                self.assertGreaterEqual(x,1156);self.assertLessEqual(x+w,1268)
                self.assertGreaterEqual(y,90);self.assertLessEqual(y+h,610)
            self.assertEqual(end[1]>start[1], r['itemName']=='mall_categories_earlier')

    def test_generated_rules_match_sources(self):
        tree=ast.parse((ROOT/'tasks/RichMan/assets.py').read_text(encoding='utf-8'))
        values={n.targets[0].id:{kw.arg:ast.literal_eval(kw.value) for kw in n.value.keywords}
                for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
        for filename,prefix in [('image_side.json','I_'),('swipe.json','S_')]:
            for r in json.loads((ROOT/'tasks/RichMan/mall/navbar'/filename).read_text(encoding='utf-8')):
                actual=values[prefix+r['itemName'].upper()]
                self.assertEqual(actual['roi_front'],tuple(map(int,r['roiFront'].split(','))))
                self.assertEqual(actual['roi_back'],tuple(map(int,r['roiBack'].split(','))))


if __name__=='__main__':unittest.main()
