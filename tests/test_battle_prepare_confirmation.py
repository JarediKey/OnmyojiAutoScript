"""Exercise delayed preparation and entry gating without an emulator."""
import ast
from pathlib import Path
import runpy
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
Timer = runpy.run_path(str(ROOT / 'module/base/timer.py'))['Timer']
GameStuckError = runpy.run_path(str(ROOT / 'module/exception.py'))['GameStuckError']


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.
        self.phase = 'prepare'
        self.ready_visible = True
        self.clicks = []
        self.ready_checks = []
        self.start_after_click = 1
        self.start_delay = .2
        self.started_at = None
        self.preset_duration = 0
        self.preset_finished = None
        self.frame_at = None
        self.sleeps = []
        self.clock = patch('time.time', side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.config = SimpleNamespace(lock_team_enable=False, preset_enable=True,
                                      preset_group=3, preset_team=3, green_enable=False,
                                      green_mark='left', random_click_swipt_enable=False)
        t = self.task = SimpleNamespace(current_count=1)
        for name in ('I_DISABLE_7DAYS_DIFF_SOUL','I_CONFIRM_CLOSE_DIFF_SOUL',
                     'I_PREPARE_HIGHLIGHT','I_WIN','I_DE_WIN','I_FALSE','I_REWARD','I_REWARD_GOLD'):
            setattr(t,name,name)
        t.screenshot = self.screenshot
        t.appear = self.appear
        t.appear_then_click = self.click
        t.is_in_prepare = lambda _: self.phase == 'prepare'
        t.is_in_real_battle = lambda _: self.phase == 'battle'
        t.is_in_battle = lambda _: self.phase in ('battle','win','false','reward')
        t.switch_preset_team = Mock(side_effect=self.preset)
        t.check_and_open_buff = Mock()
        t.green_mark = Mock()
        t.battle_wait = Mock(return_value=True)
        names = {'battle_before','_battle_started','_confirm_battle_start','run_general_battle'}
        tree = ast.parse((ROOT/'tasks/Component/GeneralBattle/general_battle.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GeneralBattle')
        body = [n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
        ns = dict(Timer=Timer,GameStuckError=GameStuckError,GeneralBattleConfig=SimpleNamespace,
                  BuffClass=object,GreenMarkType=object,logger=Mock(),sleep=self.sleep,
                  random=SimpleNamespace(uniform=lambda a,b:a))
        exec(compile(ast.Module(body=body,type_ignores=[]),'<preparation>','exec'),ns)
        for name in names:setattr(t,name,MethodType(ns[name],t))

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def screenshot(self):
        self.now += .05
        self.frame_at = self.now
        if self.started_at is not None and self.now >= self.started_at:
            self.phase = 'battle'
        assert self.now < 140, 'Preparation failed to terminate'

    def appear(self, target, **kwargs):
        return (self.phase == 'prepare' and target == 'I_PREPARE_HIGHLIGHT' and self.ready_visible
                or self.phase == 'win' and target == 'I_WIN'
                or self.phase == 'false' and target == 'I_FALSE'
                or self.phase == 'reward' and target == 'I_REWARD')

    def click(self, target, interval):
        if target != 'I_PREPARE_HIGHLIGHT':return False
        self.ready_checks.append((self.now,interval))
        if not self.appear(target):return False
        self.assertEqual(self.frame_at,self.now)
        self.clicks.append(self.now)
        if len(self.clicks) >= self.start_after_click:
            self.started_at = self.now+self.start_delay
        return True

    def preset(self, *args):
        self.now += self.preset_duration
        self.preset_finished = self.now

    def test_slow_preset_does_not_consume_entry_budget_and_click_is_delayed(self):
        self.preset_duration = 7
        self.assertTrue(self.task.battle_before(None,self.config))
        self.assertGreaterEqual(self.clicks[0]-self.preset_finished,2)
        self.task.switch_preset_team.assert_called_once_with(True,3,3)
        self.task.check_and_open_buff.assert_called_once_with(None)

    def test_ignored_first_two_clicks_get_three_spaced_attempts(self):
        self.start_after_click = 3
        self.assertTrue(self.task.battle_before(None,self.config))
        self.assertEqual(len(self.clicks),3)
        self.assertTrue(all(b-a >= 2 for a,b in zip(self.clicks,self.clicks[1:])))
        self.assertTrue(all(interval==2 for _,interval in self.ready_checks))

    def test_missing_ready_gets_three_checks_before_separate_timeout(self):
        self.ready_visible = False
        self.assertFalse(self.task.battle_before(None,self.config))
        self.assertEqual(len(self.ready_checks),3)
        self.assertGreaterEqual(self.now-self.ready_checks[-1][0],7)
        self.assertLess(self.now,115)
        self.assertEqual(self.clicks,[])

    def test_stuck_preparation_clicks_at_most_three_times(self):
        self.start_after_click = 99
        self.assertFalse(self.task.battle_before(None,self.config))
        self.assertEqual(len(self.clicks),3)
        self.assertGreaterEqual(self.now-self.clicks[-1],7)

    def test_delayed_entry_can_succeed_during_final_observation(self):
        self.start_after_click = 3
        self.start_delay = 4
        self.assertTrue(self.task.battle_before(None,self.config))
        self.assertEqual(len(self.clicks),3)
        self.assertGreaterEqual(self.now,self.started_at)

    def test_locked_team_retains_auto_start_without_preset_or_clicks(self):
        self.config.lock_team_enable = True
        self.started_at = 103
        self.assertTrue(self.task.battle_before(None,self.config))
        self.assertEqual(self.ready_checks,[])
        self.task.switch_preset_team.assert_not_called()

    def test_existing_battle_is_accepted_without_delay(self):
        self.phase = 'battle'
        self.assertTrue(self.task.battle_before(None,self.config))
        self.assertEqual(self.sleeps,[])
        self.assertEqual(self.clicks,[])

    def test_short_battle_results_during_settling_are_accepted(self):
        for result in ('win','false','reward'):
            with self.subTest(result=result):
                self.phase = 'prepare'
                def settle(seconds):
                    self.sleep(seconds)
                    self.phase = result
                original_sleep = self.sleep
                # The method's global sleep is the same bound helper shared by all methods.
                globals_=self.task._confirm_battle_start.__func__.__globals__
                globals_['sleep']=settle
                self.assertTrue(self.task.battle_before(None,self.config))
                globals_['sleep']=original_sleep
        self.assertEqual(self.clicks,[])

    def test_later_battles_do_not_reapply_preset(self):
        self.task.current_count = 2
        self.assertTrue(self.task.battle_before(None,self.config))
        self.task.switch_preset_team.assert_not_called()

    def test_failed_preparation_never_enters_result_wait_or_marking(self):
        self.ready_visible = False
        with self.assertRaisesRegex(GameStuckError,'preparation'):
            self.task.run_general_battle(self.config)
        self.task.green_mark.assert_not_called()
        self.task.battle_wait.assert_not_called()

    def test_success_preserves_recorded_defeat_result(self):
        self.phase = 'battle'
        self.task.battle_wait.return_value = False
        self.assertFalse(self.task.run_general_battle(self.config))
        self.task.battle_wait.assert_called_once_with(random_click_swipt_enable=False)

    def test_unknown_entry_page_times_out_without_clicks(self):
        self.phase = 'unknown'
        self.assertFalse(self.task.battle_before(None,self.config))
        self.assertEqual(self.ready_checks,[])
        self.task.switch_preset_team.assert_not_called()
