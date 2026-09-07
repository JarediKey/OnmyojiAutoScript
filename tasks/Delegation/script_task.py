# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd, RequestHumanTakeover
from module.atom.click import RuleClick
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_delegation
from tasks.Delegation.config import DelegationConfig
from tasks.Delegation.assets import DelegationAssets


class ScriptTask(GameUi, DelegationAssets):

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_delegation)
        self.check_reward()
        con: DelegationConfig = self.config.delegation.delegation_config
        if con.miyoshino_painting:
            self.delegate_one('画')
        if con.bird_feather:
            self.delegate_one('鸟羽')
        if con.find_earring:
            self.delegate_one('寻找耳环')
        if con.cat_boss:
            self.delegate_one('猫老大')
        if con.miyoshino:
            self.delegate_one('接送')
        if con.strange_trace:
            self.delegate_one('痕迹')


        self.set_next_run(task='Delegation', success=True, finish=True)
        raise TaskEnd

    def delegate_one(self, name: str) -> bool:
        """
        委派一个任务
        :param name:
        :return:
        """
        def ui_click(click, stop):
            while 1:
                self.screenshot()
                if self.appear(stop):
                    break
                if self.click(click, interval=1.5):
                    continue
        logger.hr('Delegation one', 2)
        self.O_D_NAME.keyword = name
        self.screenshot()
        if not self.ocr_appear(self.O_D_NAME):
            logger.warning(f'Delegation: {name} not found')
            return False
        while 1:
            self.screenshot()
            if self.appear(self.I_D_START):
                break
            # 如果出现’召回‘ ’返回‘ 说明这个是现在委派中
            # 需要退出
            if self.appear(self.I_D_BACK):
                logger.warning(f'Delegation: {name} is in delegation')
                self.ui_click_until_disappear(self.I_D_BACK)
                self.wait_until_appear(self.I_REWARDS_MIN)
                return False
            if self.appear_then_click(self.I_D_SKIP, interval=0.8):
                continue
            if self.appear_then_click(self.I_D_CONFIRM, interval=0.8):
                continue
            if self.ocr_appear_click(self.O_D_NAME, interval=1):
                continue
        # 进入委派  fefe e  fe
        logger.info(f'Enter Delegation: {name}')
        ui_click(self.C_D_1, self.I_D_SELECT_1)
        ui_click(self.C_D_2, self.I_D_SELECT_2)
        ui_click(self.C_D_3, self.I_D_SELECT_3)
        ui_click(self.C_D_4, self.I_D_SELECT_4)
        # 委派开始
        logger.info(f'Delegation: {name} start')
        while 1:
            self.screenshot()
            if not self.appear(self.I_D_START):
                break
            if self.click(self.C_D_5, interval=0.8):
                continue
            if self.appear_then_click(self.I_D_START, interval=1.8):
                continue
        # ui_click(self.C_D_5, self.I_D_SELECT_5)
        # self.ui_click_until_disappear(self.I_D_START)

    def completed_card(self):
        """Locate the first completed card without merging separate OCR matches."""
        rule = self.O_D_DONE
        results = rule.detect_and_ocr(self.device.image)
        indices = rule.filter(results, rule.keyword) if results else []
        if not indices:
            return None
        box = min((results[i].box for i in indices), key=lambda box: box[0, 1])
        x = int((box[0, 0] + box[1, 0]) / 2 + rule.roi[0])
        y = int(box[2, 1] + rule.roi[1] + 25)
        # The completion ribbon is inert; click the portrait below it.
        if not (10 <= x <= 1270 and 10 <= y <= 710):
            raise RequestHumanTakeover('Completed delegation card is outside the screen')
        area = (x - 8, y - 8, 16, 16)
        return RuleClick(roi_front=area, roi_back=area, name='delegation_completed_card')

    def check_reward(self):
        check_timer = Timer(3).start()
        progress_timer = Timer(20).start()
        attempts = 0
        entry_timer = Timer(3).start()
        reward_rules = (
            self.I_REWARDS_GET, self.I_REWARDS_CHAT, self.I_CHAT_1,
            self.I_CHAT_2, self.I_REWARDS_DONE, self.I_REWARDS_FALSE,
        )
        while 1:
            self.screenshot()
            if progress_timer.reached():
                raise RequestHumanTakeover('Delegation reward screen made no progress for 20 seconds')
            if any(self.appear_then_click(rule, interval=1) for rule in reward_rules):
                check_timer.reset()
                progress_timer.reset()
                attempts = 0
                continue
            if not self.appear(self.I_REWARDS_MIN):
                continue
            card = self.completed_card()
            if card is not None:
                check_timer.reset()
                if not entry_timer.reached():
                    continue
                if attempts >= 3:
                    raise RequestHumanTakeover('Completed delegation did not open after 3 clicks')
                self.click(card)
                entry_timer.reset()
                attempts += 1
                logger.info(f'Open completed delegation card, attempt {attempts}/3')
                continue
            if attempts:
                # A missing ribbon alone does not prove that rewards were collected.
                continue
            if check_timer.reached():
                break


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    # t.delegate_one('弥助的画')
    t.run()



