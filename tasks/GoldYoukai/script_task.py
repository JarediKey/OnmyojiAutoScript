# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from cached_property import cached_property

from module.exception import TaskEnd, GameStuckError
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_team, page_shikigami_records
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GoldYoukai.assets import GoldYoukaiAssets
from tasks.GoldYoukai.config import GoldYoukaiConfig


class ScriptTask(GameUi, GeneralBattle, GeneralRoom, GeneralInvite, SwitchSoul, GoldYoukaiAssets):

    def run(self):
        # 切换御魂
        if self.config.gold_youkai.switch_soul.enable:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(self.config.gold_youkai.switch_soul.switch_group_team)

        if self.config.gold_youkai.switch_soul.enable_switch_by_name:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(self.config.gold_youkai.switch_soul.group_name,
                                         self.config.gold_youkai.switch_soul.team_name)

        # 开启加成
        con = self.config.gold_youkai.gold_youkai
        if con.buff_gold_50_click or con.buff_gold_100_click:
            self.goto_page(page_main)
            self.open_buff()
            if con.buff_gold_50_click:
                self.gold_50()
            if con.buff_gold_100_click:
                self.gold_100()
            self.close_buff()
        count = 0
        while count < 2:
            self.goto_page(page_team)
            self.check_zones('金币妖怪')
            # 开始
            if not self.create_room():
                self.gold_exit(con)
            self.ensure_public()
            self.create_ensure()
            self.wait_for_full_team()
            count += 1
            self.run_general_battle()
        # 退出 (要么是在组队界面要么是在庭院)
        self.gold_exit(con)


    def wait_for_full_team(self):
        """Start at five players, or after 180 seconds; confirm actual battle entry."""
        wait_timer = Timer(180).start()
        full_timer = Timer(2, count=2)
        entry_timer = Timer(15)
        slots = (self.I_ADD_5_1, self.I_ADD_5_2, self.I_ADD_5_3, self.I_ADD_5_4)
        self.device.stuck_record_clear()
        self.device.stuck_record_add('PREPARE_BEFORE_BATTLE')
        logger.info('Wait for five players; start after at most 180 seconds')
        try:
            while True:
                self.screenshot()
                if self.is_in_prepare(False) or self.is_in_real_battle(False):
                    logger.info('GoldYoukai battle entry confirmed')
                    return
                if entry_timer.started() and entry_timer.reached():
                    raise GameStuckError('GoldYoukai challenge did not enter battle within 15 seconds')

                in_room = self.is_in_room(False) or self.appear(self.I_GI_IN_ROOM)
                expired = wait_timer.reached()
                if not in_room:
                    full_timer.clear()
                    if expired and not entry_timer.started():
                        raise GameStuckError('GoldYoukai room not confirmed after 180 seconds')
                    continue

                full = not any(self.appear(slot) for slot in slots)
                if full and self.appear(self.I_FIRE, threshold=0.7):
                    full_timer.start()
                    ready = full_timer.reached()
                else:
                    full_timer.clear()
                    ready = False
                if not ready and not expired:
                    continue
                if not entry_timer.started():
                    logger.info('GoldYoukai full team confirmed' if ready else
                                'GoldYoukai waited 180 seconds; start with current players')
                    entry_timer.start()
                if self.appear_then_click(self.I_FIRE, interval=2, threshold=0.7):
                    self.device.stuck_record_add('PREPARE_BEFORE_BATTLE')
        finally:
            self.device.stuck_record_clear()

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        # 战斗过程 随机点击和滑动 防封
        logger.info("Start battle process")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=1):
                logger.info('click prepare')
            if self.appear(self.I_DE_WIN):
                logger.info('Win battle')
                self.ui_click_until_disappear(self.I_DE_WIN)
                return True
            if self.appear(self.I_GOLD_WIN):
                logger.info('Win battle')
                self.ui_click_until_disappear(self.I_GOLD_WIN)
                return True

            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False

    def gold_exit(self, con):
        self.goto_page(page_main)
        if con.buff_gold_50_click or con.buff_gold_100_click:
            self.open_buff()
            if con.buff_gold_50_click:
                self.gold_50(False)
            if con.buff_gold_100_click:
                self.gold_100(False)
            self.close_buff()

        self.set_next_run(task='GoldYoukai', success=True, finish=False)
        raise TaskEnd('GoldYoukai')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
