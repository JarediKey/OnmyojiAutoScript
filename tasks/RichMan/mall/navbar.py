# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
import time

from module.logger import logger
from module.base.timer import Timer
from module.exception import GameStuckError

from tasks.GameUi.page import page_main, page_guild, page_mall
from tasks.GameUi.game_ui import GameUi
from tasks.Component.Buy.buy import Buy
from tasks.RichMan.assets import RichManAssets



class MallNavbar(GameUi, RichManAssets):

    def _enter_consignment(self):
        """
        进入寄售屋
        :return:
        """
        self.ui_click(self.I_MALL_CONSIGNMENT, self.I_MALL_CONSIGNMENT_CHECK)

    def _enter_scales(self):
        """
        进入密卷屋 蛇皮
        :return:
        """
        self.ui_click(self.I_MALL_SCCALES, self.I_MALL_SCCALES_CHECK)

    def _enter_bondlings(self):
        """
        进入契灵
        :return:
        """
        self._enter_scales()
        self.ui_click(self.I_MALL_BONDLINGS_SURE, self.I_MALL_BONDLINGS_ON)

    def _enter_sundry(self):
        """
        进入杂货铺
        :return:
        """
        self.ui_click(self.I_MALL_SUNDRY, self.I_MALL_SUNDRY_CHECK)

    def _enter_special(self):
        self._enter_sundry_category('special')

    def _enter_honor(self):
        self._enter_sundry_category('duel')

    def _enter_friendship(self):
        self._enter_sundry_category('friendship')

    def _enter_medal(self):
        self._enter_sundry_category('medal')

    def _enter_charisma(self):
        self._enter_sundry_category('charisma')

    def _sundry_categories(self):
        """Primary categories in sidebar order; Duel's children are not categories."""
        return (
            ('special', self.I_SIDE_SURE_SPECIAL),
            ('duel', self.I_SIDE_SUER_HONOR),
            ('friendship', self.I_SIDE_SURE_FRIENDS),
            ('medal', self.I_SIDE_SURE_MEDAL),
            ('charisma', self.I_SIDE_SURE_CHARISMA),
        )

    def _read_sundry_sidebar(self):
        """Associate the primary-tab highlight with a recognized category label."""
        categories = self._sundry_categories()
        visible = {name: button for name, button in categories if self.appear(button)}
        order = {name: index for index, (name, _) in enumerate(categories)}
        positions = sorted(visible, key=lambda name: visible[name].roi_front[1])
        if [order[name] for name in positions] != sorted(order[name] for name in visible):
            return {}, None
        selected = None
        if self.appear(self.I_MALL_CATEGORY_SELECTED):
            _, y, _, height = self.I_MALL_CATEGORY_SELECTED.roi_front
            middle = y + height / 2
            matches = [name for name, button in visible.items()
                       if button.roi_front[1] <= middle <= button.roi_front[1] + button.roi_front[3]]
            if len(matches) == 1:
                selected = matches[0]
        return visible, selected

    def _enter_sundry_category(self, target):
        """Reveal hidden tabs in the required direction, then confirm selection."""
        self._enter_sundry()
        order = [name for name, _ in self._sundry_categories()]
        target_index = order.index(target)
        timeout = Timer(25).start()
        ready = Timer(1, count=2).start()
        click_wait = Timer(3)
        swipes = clicks = 0
        previous = None
        while not timeout.reached():
            self.screenshot()
            visible, selected = self._read_sundry_sidebar()
            state = (tuple(visible), selected)
            if state != previous:
                logger.info(f'Shop sidebar visible={list(visible)}, selected={selected or "unknown"}, target={target}')
                previous = state
            if selected == target:
                if ready.reached():
                    return
                continue
            ready.reset()
            if clicks >= 3 and click_wait.reached():
                raise GameStuckError(f'Shop category {target} not selected after 3 clicks')
            if target in visible:
                if clicks < 3 and click_wait.reached():
                    self.click(visible[target])
                    clicks += 1
                    click_wait.reset()
                continue
            # After clicking, allow the UI to settle without scrolling it away.
            if clicks or not visible:
                continue
            indices = [order.index(name) for name in visible]
            if target_index < min(indices):
                swipe = self.S_MALL_CATEGORIES_EARLIER
            elif target_index > max(indices):
                swipe = self.S_MALL_CATEGORIES_LATER
            else:
                # A missing label inside the visible range is ambiguous.
                continue
            if swipes >= 3:
                raise GameStuckError(f'Shop category {target} not found after 3 sidebar swipes')
            self.swipe(swipe)
            swipes += 1
            time.sleep(1)
        raise GameStuckError(f'Shop category {target} not confirmed within 25 seconds')

    def back_mall(self):
        """Finish shop cleanup at either the mall or the courtyard."""
        timeout = Timer(20).start()
        while True:
            self.screenshot()
            for page in (page_mall, page_main):
                if self.ui_page_appear(page):
                    self.ui_current = page
                    logger.info(f'Shop return complete: {page}')
                    return
            if timeout.reached():
                raise GameStuckError('Shop return did not reach the mall or courtyard within 20 seconds')
            self.appear_then_click(self.I_UI_BACK_YELLOW, interval=3)

    def mall_resource(self, index: int) -> int:
        """
        获取商城资源，
        :param index: 从左开始数
        :return:
        """
        match = {
            1: self.O_MALL_RESOURCE_1,
            2: self.O_MALL_RESOURCE_2,
            3: self.O_MALL_RESOURCE_3,
            4: self.O_MALL_RESOURCE_4,
            5: self.O_MALL_RESOURCE_5,
            6: self.O_MALL_RESOURCE_6,
            7: self.O_MALL_RESOURCE_7,
        }
        self.screenshot()
        result = match[index].ocr(self.device.image)
        # match = re.search(r'\d+', result)
        # result = int(match.group())
        if not isinstance(result, int):
            logger.warning(f'Get mall resource {index} error, result: {result}')
        if result == 0:
            logger.warning(f'Get mall resource {index} error, result: {result}')
        return result

    def mall_check_money(self, index: int, least: int) -> bool:
        return self.mall_resource(index) >= least
    
    #add legacy check money method for compatibility, for consignment task
    def mall_check_money_legacy(self, index: int, least: int) -> bool:
        """
        Legacy implementation.
        旧版商城资源判断逻辑（包含资源获取 + 校验）用于插画屋和寄售屋任务
        :param index: 从左开始数 1-4 对应第1-4个资源 least 最少多少
        :return: bool
        """

        match = {
            1: self.O_LEGACY_MALL_RESOURCE_1,
            2: self.O_LEGACY_MALL_RESOURCE_2,
            3: self.O_LEGACY_MALL_RESOURCE_3,
            4: self.O_LEGACY_MALL_RESOURCE_4,
        }

        self.screenshot()
        result = match[index].ocr(self.device.image)

        if not isinstance(result, int):
            logger.warning(f'Get mall resource {index} error, result: {result}')
            return False

        if result == 0:
            logger.warning(f'Get mall resource {index} error, result: {result}')
            return False

        return result >= least

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = MallNavbar(c, d)
