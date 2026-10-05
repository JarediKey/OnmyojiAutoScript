# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import cv2
import numpy as np

from tasks.Component.GeneralBuff.assets import GeneralBuffAssets
from module.atom.ocr import RuleOcr
from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.base.timer import Timer
from tasks.base_task import BaseTask
from module.logger import logger


class GeneralBuff(BaseTask, GeneralBuffAssets):

    def open_buff(self):
        """
        打开buff的总界面
        :return:
        """
        logger.info('Open buff')
        while 1:
            self.screenshot()
            if self.appear(self.I_CLOUD):
                break
            if self.appear_then_click(self.I_BUFF_1, interval=2):
                continue

        check_image = self.I_AWAKE
        while 1:
            self.screenshot()
            if self.appear(check_image):
                break

            self.swipe(self.S_BUFF_UP, interval=2)

    def close_buff(self):
        """
        关闭buff的总界面, 但是要确保buff界面已经打开了
        :return:
        """
        logger.info('Close buff')
        while 1:
            self.screenshot()
            if not self.appear(self.I_CLOUD):
                break
            if self.appear_then_click(self.I_BUFF_1, interval=2):
                continue

    def get_area(self, buff: RuleOcr) -> tuple:
        """
        获取要点击的开关buff的区域
        :param cls:
        :param image:
        :param buff:
        :return:  如果没有就返回None
        """
        # 防止邀请框挡住BUFF框架
        self.reject_invite()
        self.screenshot()
        area = buff.ocr(self.device.image)
        if area == tuple([432.0, 143.0, 325.0, 21.0]):
            logger.info(f'No {buff.name} buff')
            return None

        # At 1280x720 the round controls have a fixed column, independent of text width.
        return 844, int(area[1] - 10), 60, int(area[3] + 20)

    def set_switch_area(self, area):
        """
        设置开关的区域
        :param area:
        :return:
        """
        self.I_OPEN_YELLOW.roi_back = list(area)  # 动态设置roi
        self.I_CLOSE_RED.roi_back = list(area)

    def _set_buff_switch(self, is_open: bool) -> bool:
        """Click a verified round control and confirm its new state on a fresh frame."""
        expected = self.I_OPEN_YELLOW if is_open else self.I_CLOSE_RED
        opposite = self.I_CLOSE_RED if is_open else self.I_OPEN_YELLOW
        timer = Timer(10).start()
        attempts = 0
        while not timer.reached():
            self.screenshot()
            if self.appear(expected):
                return True
            if attempts < 3 and self.appear(opposite):
                x, y = opposite.front_center()
                area = (x - 4, y - 4, 8, 8)
                button = RuleClick(area, area, name=opposite.name)
                if self.click(button, interval=2):
                    attempts += 1
                    time.sleep(2)
            else:
                time.sleep(0.3)
        logger.warning(f'Buff switch not confirmed after {attempts} clicks')
        return False

    def gold_50(self, is_open: bool = True):
        """
        金币50buff
        :param is_open: 是否打开
        :return:
        """
        logger.info(f'{"Open" if is_open else "Close"} gold 50 buff')
        self.screenshot()
        area = self.get_area(self.O_GOLD_50)
        if not area:
            logger.warning('No gold 50 buff')
            return None
        self.set_switch_area(area)
        if not self._set_buff_switch(is_open):
            logger.warning(f'{"Open" if is_open else "Close"} gold 50 buff failed')

    def gold_100(self, is_open: bool = True):
        """
        金币100buff
        :param is_open: 是否打开
        :return:
        """
        logger.info(f'{"Open" if is_open else "Close"} gold 100 buff')
        self.screenshot()
        area = self.get_area(self.O_GOLD_100)
        if not area:
            logger.warning('No gold 100 buff')
            return None
        self.set_switch_area(area)
        if not self._set_buff_switch(is_open):
            logger.warning(f'{"Open" if is_open else "Close"} gold 100 buff failed')

    def exp_50(self, is_open: bool = True):
        """
        经验50buff
        :param is_open: 是否打开
        :return:
        """
        logger.info(f'{"Open" if is_open else "Close"} exp 50 buff')
        while 1:
            self.screenshot()
            area = self.get_area(self.O_EXP_50)
            if not area:
                logger.warning('No exp 50 buff')
                continue
            self.set_switch_area(area)

            if not self.appear(self.I_OPEN_YELLOW) and not self.appear(self.I_CLOSE_RED):
                self.device.swipe(p2=(530, 240), p1=(580, 320))
                time.sleep(1)
            else:
                break

        if not self._set_buff_switch(is_open):
            logger.warning(f'{"Open" if is_open else "Close"} exp 50 buff failed')

    def exp_100(self, is_open: bool = True):
        """
        经验100buff
        :param is_open: 是否打开
        :return:
        """
        logger.info(f'{"Open" if is_open else "Close"} exp 100 buff')
        while 1:
            self.screenshot()
            area = self.get_area(self.O_EXP_100)
            if not area:
                logger.warning('No exp 100 buff')
                continue
            self.set_switch_area(area)

            if not self.appear(self.I_OPEN_YELLOW) and not self.appear(self.I_CLOSE_RED):
                self.device.swipe(p2=(530, 240), p1=(580, 320))
                time.sleep(1)
            else:
                break

        if not self._set_buff_switch(is_open):
            logger.warning(f'{"Open" if is_open else "Close"} exp 100 buff failed')

    def get_area_image(self, target: RuleImage) -> list:
        """
        获取觉醒加成或者是御魂加成所要点击的区域
        因为实在的图片比ocr快
        :param image:
        :param target:
        :return:
        """
        self.reject_invite()
        self.screenshot()

        if not target.match(self.device.image):
            logger.warning(f'No {target.name} buff')
            return None
            # logger.info(f'front area: {target.roi_front}')
            # logger.info(f'front center: {target.front_center()}')
        return [844, int(target.roi_front[1]), 60, int(target.roi_front[3])]

    def awake(self, is_open: bool = True):
        """
        觉醒buff
        :param is_open: 是否打开
        :return:
        """
        logger.info(f'{"Open" if is_open else "Close"} awake buff')
        self.screenshot()
        area = self.get_area_image(self.I_AWAKE)
        if not area:
            logger.warning('No awake buff')
            return None
        self.set_switch_area(area)
        if not self._set_buff_switch(is_open):
            logger.warning(f'{"Open" if is_open else "Close"} awake buff failed')

    def soul(self, is_open: bool = True):
        """
        御魂buff
        :param is_open: 是否打开
        :return:
        """
        logger.info(f'{"Open" if is_open else "Close"} soul buff')
        self.screenshot()
        area = self.get_area_image(self.I_SOUL)
        if not area:
            logger.warning('No soul buff')
            return None
        self.set_switch_area(area)
        if not self._set_buff_switch(is_open):
            logger.warning(f'{"Open" if is_open else "Close"} soul buff failed')

    def reject_invite(self):
        from tasks.Component.GeneralInvite.assets import GeneralInviteAssets as gia
        while 1:
            self.screenshot()
            if not (self.appear(gia.I_I_REJECT_1) or self.appear(gia.I_I_REJECT_2) or self.appear(gia.I_I_REJECT_3)):
                break
            if self.appear(gia.I_I_REJECT_3):
                self.click(gia.I_I_REJECT_3, 6)
                continue
            if self.appear(gia.I_I_REJECT_2):
                self.click(gia.I_I_REJECT_2, 6)
                continue
            if self.appear(gia.I_I_REJECT_1):
                self.click(gia.I_I_REJECT_1, 6)
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = GeneralBuff(c, d)

    t.open_buff()
    # t.screenshot()
    #
    t.awake(is_open=True)
    t.soul(is_open=True)
    t.gold_50(is_open=False)
    t.gold_100(is_open=False)
    t.exp_50(is_open=True)
    t.exp_100(is_open=True)
