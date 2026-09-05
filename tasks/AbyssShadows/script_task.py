# This Python file uses the following encoding: utf-8
# @brief    AbyssShadows(阴阳竂狭间暗域功能)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas
from time import sleep

from datetime import datetime, timedelta
from pathlib import Path
from module.exception import TaskEnd, RequestHumanTakeover
from module.base.timer import Timer
from module.logger import logger
from module.config.config import Config
from module.device.device import Device
from tasks.AbyssShadows.assets import AbyssShadowsAssets
from tasks.AbyssShadows.config import AbyssShadows, EnemyType, AreaType, Code, AbyssShadowsDifficulty, \
    CodeList, IndexMap
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_guild

# 单个首领/副将/精英 一次无法完成目标（一般是一次没打掉） 的情况下，最大战斗次数
MAX_BATTLE_COUNT = 2
MAX_BATTLE_WAIT = 300
MAX_ENTRY_WAIT = 30


class AbyssShadowsFinished(Exception):
    pass


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, AbyssShadowsAssets):
    #
    min_count = {
        EnemyType.BOSS: 2,  # 最少首领战斗次数
        EnemyType.GENERAL: 4,  # 最少副将战斗次数
        EnemyType.ELITE: 6  # 最少精英战斗次数
    }

    def __init__(self, config: Config, device: Device):
        super().__init__(config, device)
        # 当前所用队伍预设
        self.cur_preset = None
        # process list
        self.ps_list: CodeList = CodeList('')
        # 已完成 列表
        self.done_list: CodeList = CodeList('')
        # 已知的 已经被打完的  列表
        self.unavailable_list: CodeList = CodeList('')
        self.failed_list: CodeList = CodeList('')
        # 是否已经切换过御魂
        self.switch_soul_done = False

    def click(self, click=None, interval=None):
        """Slow action retries only in Abyss, including shared component calls."""
        return super().click(click, interval=interval * 2 if interval else interval)

    def appear_then_click(self, target, action=None, interval=None, threshold=None, duration=None):
        return super().appear_then_click(
            target, action=action, interval=interval * 2 if interval else interval,
            threshold=threshold, duration=duration)

    def swipe(self, swipe, interval=None):
        return super().swipe(swipe, interval=interval * 2 if interval else interval)

    def request_takeover(self, stage: str, reason: str):
        """Preserve the current frame without device input or notification side effects."""
        from module.base.utils import save_image
        from module.handler.sensitive_info import handle_sensitive_image

        logger.error(f'Abyss stage={stage}: {reason}')
        try:
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            folder = Path('log/error/abyss') / f'{self.config.config_name}-{stamp}'
            folder.mkdir(parents=True, exist_ok=False)
            save_image(handle_sensitive_image(self.device.image.copy()), str(folder / f'{stage}.png'))
            logger.info(f'Abyss diagnostic frame: {folder}')
        except Exception as exc:
            logger.warning(f'Could not save Abyss diagnostic frame: {exc}')
        raise RequestHumanTakeover(f'Abyss {stage}: {reason}')

    def battle_entry_state(self) -> str:
        """Inspect the current frame; an exit button alone is not proof of battle."""
        if self.appear(self.I_WIN) or self.appear(self.I_FALSE) or self.appear(self.I_REWARD):
            return 'result'
        if self.appear(self.I_PRESET_ENSURE):
            return 'preset'
        if self.appear(self.I_PREPARE_HIGHLIGHT):
            return 'prepare'
        if self.appear(self.I_PREPARE_DARK):
            return 'prepare_loading'
        if self.appear(self.I_BATTLE_INFO):
            return 'battle'
        if self.appear(self.I_EXIT):
            return 'transition'
        return 'unknown'

    def enter_battle(self, item_code: Code):
        """Handle manual preparation or locked-team auto-entry without blind clicks."""
        process = self.config.model.abyss_shadows.process_manage
        preset = {
            EnemyType.BOSS: process.preset_boss,
            EnemyType.GENERAL: process.preset_general,
            EnemyType.ELITE: process.preset_elite,
        }[item_code.get_enemy_type()]
        timer = Timer(MAX_ENTRY_WAIT).start()
        previous_state = None
        pending_preset = None
        while True:
            self.screenshot()
            state = self.battle_entry_state()
            if state != previous_state:
                logger.info(f'Abyss entry {item_code}: {state}, lock_team={process.lock_team_enable}')
                previous_state = state
            if pending_preset and state in ('prepare', 'battle', 'result'):
                self.cur_preset = pending_preset
                pending_preset = None
            if state in ('battle', 'result'):
                return
            if timer.reached():
                self.request_takeover('entry', f'{item_code}: no battle confirmation after {MAX_ENTRY_WAIT}s; state={state}')
            if state != 'prepare':
                continue
            if not process.lock_team_enable and preset and preset != self.cur_preset:
                self.switch_preset_team_with_str(preset)
                pending_preset = preset
                # Never act on the frame preceding the preset animation.
                continue
            self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=0.6)

    def exit_abyss_records(self):
        """Leave records only while its own page marker is visible."""
        timer = Timer(MAX_ENTRY_WAIT).start()
        previous_state = None
        while True:
            self.screenshot()
            in_records = self.appear(self.I_SOU_CHECK_IN)
            on_map = self.appear(self.I_ABYSS_NAVIGATION) and self.appear(self.I_ABYSS_SHIKI)
            if on_map and not in_records:
                logger.info('Abyss records exit: map confirmed')
                return
            state = 'records' if in_records else 'transition'
            if state != previous_state:
                logger.info(f'Abyss records exit: {state}')
                previous_state = state
            if timer.reached():
                self.request_takeover('records-exit', f'no map confirmation after {MAX_ENTRY_WAIT}s; state={state}')
            if in_records:
                self.appear_then_click(self.I_RECORD_SOUL_BACK, interval=2)

    def run(self):
        """ 狭间暗域主函数

        :return:
        """
        cfg: AbyssShadows = self.config.abyss_shadows

        today = datetime.now().weekday()
        if today not in [4, 5, 6]:
            # 非周五六日，直接退出
            logger.info(f"Today is not abyss shadows day, exit")
            self.set_next_run(task='AbyssShadows', finish=False, server=True, success=True)
            raise TaskEnd
        # Trial startup is controlled by the operator; avoid the old implicit
        # two-hour cutoff based on the scheduler's special 09:00 default.

        # 进入狭间
        self.goto_abyss_shadows()

        # 尝试开启狭间
        if cfg.abyss_shadows_time.try_start_abyss_shadows:
            self.start_abyss_shadows()

        try:
            self.init_list_from_cfg()
            # 判断各个区域是否可用
            available_areas, unavailable_areas = self.detect_area_status()
            for area in unavailable_areas:
                self.unavailable_list += CodeList(IndexMap[area.name].value)
            if unavailable_areas:
                self.flash_list()

            # 获取需要进入的区域类型
            _next = self.get_next()
            if _next is None:
                raise AbyssShadowsFinished
            area_enter = _next.get_areatype()

            # 通过能否进入，检测狭间是否开启
            if not self.select_boss(area_enter):
                logger.warning("Failed to enter abyss shadows")
                self.goto_main()
                if cfg.process_manage.trial_mode:
                    raise RequestHumanTakeover('Abyss trial could not enter the requested region')
                self.set_next_run(task='AbyssShadows', finish=False, server=False, success=False)
                raise TaskEnd

            # 集结中图片
            self.wait_until_appear(self.I_WAIT_TO_START, wait_time=2)

            # 检查活动是否结束
            if self.appear(self.I_CHECK_FINISH):
                logger.info(f"{self.I_CHECK_FINISH} appear,abyss shadows finished")
                raise AbyssShadowsFinished
            # 切换御魂
            self.switch_soul_in_as()
            #
            self.device.stuck_record_add('BATTLE_STATUS_S')
            # 等待战斗开始
            if not self.wait_until_appear(self.I_IS_ATTACK, wait_time=180):
                raise RequestHumanTakeover('Abyss did not reach the attack phase within 180s')
            self.device.stuck_record_clear()
            #
            self.process()
        except AbyssShadowsFinished:
            logger.info("Abyss shadows finished with Exception AbyssShadowsFinished")
            pass
        logger.info("Abyss shadows process done")

        # 保持好习惯，一个任务结束了就返回到庭院，方便下一任务的开始
        self.goto_main()

        # 设置下次运行时间
        if cfg.process_manage.trial_mode:
            self.flash_list()
            raise RequestHumanTakeover('Abyss trial finished; inspect the recording and saved target states')
        self.set_next_run(task='AbyssShadows', finish=True, server=True,
                          success=not self.failed_list)
        if not self.failed_list:
            self.clear_saved_params()

        raise TaskEnd

    def init_list_from_cfg(self):
        if datetime.today().strftime('%Y-%m-%d') != self.config.model.abyss_shadows.saved_params.save_date:
            logger.info("Today is not saved date, clear saved params")
            self.clear_saved_params()
        #
        self.ps_list = CodeList(self.config.model.abyss_shadows.process_manage.attack_order)
        #
        self.done_list = CodeList(self.config.model.abyss_shadows.saved_params.done)
        #
        self.unavailable_list = CodeList(self.config.model.abyss_shadows.saved_params.unavailable)
        self.failed_list = CodeList(self.config.model.abyss_shadows.saved_params.failed)
        logger.info(f"update list done!{self.done_list=} {self.unavailable_list=}")

    def flash_list(self):
        """
            NOTE 导致该任务运行过程中，从前端修改的配置将会丢失
        @return:
        """
        # Reload before updating progress so unrelated saved settings are retained.
        self.config.reload()
        self.config.model.abyss_shadows.saved_params.save_date = datetime.today().strftime('%Y-%m-%d')
        self.config.model.abyss_shadows.saved_params.done = self.done_list.parse2str()
        self.config.model.abyss_shadows.saved_params.unavailable = self.unavailable_list.parse2str()
        self.config.model.abyss_shadows.saved_params.failed = self.failed_list.parse2str()

        self.config.save()
        logger.info(f"Flash list done!{self.done_list=} {self.unavailable_list=}")

    def clear_saved_params(self):
        self.config.model.abyss_shadows.saved_params.done = ''
        self.config.model.abyss_shadows.saved_params.unavailable = ''
        self.config.model.abyss_shadows.saved_params.failed = ''
        self.config.model.abyss_shadows.saved_params.save_date = datetime.today().strftime('%Y-%m-%d')
        self.config.save()
        logger.info("Clear saved params done")

    def check_current_area(self) -> AreaType:
        """ 获取当前区域
        :return AreaType
        """
        while 1:
            self.screenshot()
            # 关闭战报界面
            if self.appear(self.I_ABYSS_MAP_EXIT):
                self.click(self.I_ABYSS_MAP_EXIT, interval=2)
                continue
            if self.appear(self.I_ABYSS_ENEMY_INFO_EXIT):
                self.click(self.I_ABYSS_ENEMY_INFO_EXIT, interval=2)
                continue
            if not self.appear(self.I_ABYSS_NAVIGATION):
                # 确定不在战报界面后依旧没有在某一区域，则返回None
                return None
            if self.appear(self.I_PEACOCK_AREA):
                return AreaType.PEACOCK
            elif self.appear(self.I_DRAGON_AREA):
                return AreaType.DRAGON
            elif self.appear(self.I_FOX_AREA):
                return AreaType.FOX
            elif self.appear(self.I_LEOPARD_AREA):
                return AreaType.LEOPARD

    def change_area(self, area_name: AreaType) -> bool:
        """ 切换到下个区域,不管成功与否,只要存在可用区域,就进入,不会停留在选择区域页面
        :return
        """
        # 确保进入区域,有 切换区域 按钮
        while 1:
            self.screenshot()
            # 如果出现挑战完成，直接退出
            if self.appear(self.I_CHECK_FINISH):
                raise AbyssShadowsFinished

            if self.appear(self.I_ABYSS_NAVIGATION) or self.appear(self.I_CHANGE_AREA):
                break
            #
            if self.appear(self.I_ABYSS_MAP_EXIT):
                self.click(self.I_ABYSS_MAP_EXIT, interval=2)
                continue
            #
            if self.appear(self.I_ABYSS_ENEMY_INFO_EXIT):
                self.click(self.I_ABYSS_ENEMY_INFO_EXIT, interval=2)
                continue

        # 判断当前区域是否正确
        current_area = self.check_current_area()
        if current_area == area_name:
            return True

        # 切换到选择区域界面
        while 1:
            self.screenshot()
            # 如果出现挑战完成，直接退出
            if self.appear(self.I_CHECK_FINISH):
                raise AbyssShadowsFinished

            # 出现切换区域界面
            if self.appear(self.I_ABYSS_DRAGON_OVER) or self.appear(self.I_ABYSS_DRAGON):
                break
            # 点击切换区域按钮
            if self.appear_then_click(self.I_CHANGE_AREA, interval=4):
                logger.info(f"Click {self.I_CHANGE_AREA.name}")
                continue

        # 判断区域是否可用，并进入一个区域
        available_areas, unavailable_areas = self.detect_area_status()
        success = area_name in available_areas
        if not success:
            # 更新配置
            for area in unavailable_areas:
                self.unavailable_list += CodeList(IndexMap[area.name].value)

        if available_areas is None or available_areas == []:
            # 所有区域均不可用
            raise AbyssShadowsFinished

        if not success:
            # 原参数表示的 区域 已完成，则选择第一个未完成的区域
            area_name = available_areas[0]

        self.select_boss(area_name)
        logger.info(f"Switch to {area_name.name}")

        return success

    def goto_main(self):
        """ 保持好习惯，一个任务结束了就返回庭院，方便下一任务的开始或者是出错重启
        """
        # 可能在狭间，也可能在其他界面
        timer_quit_abyss_shadows = Timer(16)
        timer_quit_abyss_shadows.start()
        while 1:
            self.screenshot()
            if timer_quit_abyss_shadows.reached():
                logger.info("timer_quit_abyss_shadows reached,")
                break
            if self.appear(self.I_ABYSS_NAVIGATION) or self.appear(self.I_CHECK_FINISH):
                break
            if self.appear(self.I_CHECK_SUMMON):
                break
            if self.appear(self.I_ABYSS_DRAGON) or self.appear(self.I_ABYSS_DRAGON_OVER):
                # 在切换区域界面
                self.device.click(x=600, y=600)
                self.wait_until_appear(self.I_ABYSS_NAVIGATION, wait_time=2)
                continue
            if self.appear_then_click(self.I_ABYSS_MAP_EXIT, interval=2):
                continue
            if self.appear_then_click(self.I_ABYSS_ENEMY_INFO_EXIT, interval=2):
                continue
            if self.appear_then_click(self.I_UI_BACK_BLUE, interval=2):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2):
                continue

        #
        logger.info("Exiting abyss_shadows")
        self.ui_get_current_page()
        self.ui_goto(page_main)

    def goto_abyss_shadows(self) -> bool:
        """ 进入狭间
        :return bool
        """
        self.ui_get_current_page()
        logger.info("Entering abyss_shadows")
        self.ui_goto(page_guild)

        while 1:
            self.screenshot()
            # Upstream fix: Shenshe can resume an already active map directly.
            if self.appear(self.I_ABYSS_NAVIGATION):
                logger.info('Already in abyss_shadows')
                break
            # 进入神社
            if self.appear_then_click(self.I_RYOU_SHENSHE, interval=1):
                logger.info("Enter Shenshe")
                continue
            # 查找狭间
            if not self.appear(self.I_ABYSS_SHADOWS, threshold=0.8):
                self.swipe(self.S_TO_ABBSY_SHADOWS, interval=3)
                continue
            # 进入狭间
            if self.appear_then_click(self.I_ABYSS_SHADOWS, interval=1):
                logger.info("Enter abyss_shadows")
                break
        return True

    def select_boss(self, area_name: AreaType) -> bool:
        """ 选择暗域类型
        :return
        """
        click_times = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_ABYSS_NAVIGATION):
                return True
            # 区域图片与入口图片不一致，使用点击进去
            if self.appear(self.I_ABYSS_DRAGON_OVER) or self.appear(self.I_ABYSS_DRAGON):
                is_click = False
                match area_name:
                    case AreaType.DRAGON:
                        is_click = self.click(self.C_ABYSS_DRAGON, interval=2)
                    case AreaType.PEACOCK:
                        is_click = self.click(self.C_ABYSS_PEACOCK, interval=2)
                    case AreaType.FOX:
                        is_click = self.click(self.C_ABYSS_FOX, interval=2)
                    case AreaType.LEOPARD:
                        is_click = self.click(self.C_ABYSS_LEOPARD, interval=2)
                if is_click:
                    click_times += 1
                    logger.info(f"Click {area_name.name} {click_times} times")
                if click_times >= 3:
                    logger.info(f"select boss: {area_name.name} failed")
                    return False
                continue
            if self.appear(self.I_ABYSS_NAVIGATION):
                break
        return True

    def goto_enemy(self, item_code: Code) -> bool:
        # 前往当前区域 的某个 敌人
        click_area = item_code.get_enemy_click()
        logger.info(f"Click emeny area: {click_area.name}")
        # 点击前往按钮的次数，阴阳师BUG:点击后不动，
        # 所以如果失败了，在点击前，尝试使用左下方的摇杆移动一点点
        count_click_goto_enemy = 0
        # 点击战报
        while 1:
            self.screenshot()
            if self.appear(self.I_ABYSS_FIRE):
                break
            # 尝试使用左下方摇杆移动
            if count_click_goto_enemy > 0 and self.appear(self.I_ABYSS_NAVIGATION):
                self.move_a_little()
            # 打开导航页面
            self.open_navigation()

            click_times = 0
            # 点击攻打区域,直到出现"前往"字样
            while 1:
                self.screenshot()
                if self.appear(self.I_ABYSS_GOTO_ENEMY):
                    break
                # 如果点3次还没进去就表示目标已死亡,跳过
                if click_times >= 3:
                    logger.warning(f"Failed to click {click_area}")
                    return False
                # 出现前往按钮就退出
                if self.appear(self.I_ABYSS_GOTO_ENEMY):
                    break
                if self.click(click_area, interval=1.5):
                    click_times += 1
                    continue
                if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                    continue

            # 点击前往按钮,知道该按钮消失或出现"挑战"字样

            while 1:
                self.screenshot()
                if self.appear(self.I_CHECK_FINISH):
                    raise AbyssShadowsFinished
                if self.appear(self.I_ABYSS_FIRE):
                    break
                if self.appear(self.I_ENSURE_BUTTON):
                    self.click(self.I_ENSURE_BUTTON, interval=1)
                    continue
                if self.appear(self.I_ABYSS_GOTO_ENEMY):
                    self.click(self.I_ABYSS_GOTO_ENEMY, interval=1)
                    count_click_goto_enemy += 1
                    continue
                if not self.wait_until_appear(self.I_ABYSS_FIRE, wait_time=10):
                    break
        return True

    def attack_enemy(self):
        # Locked teams may bypass the preparation page entirely.
        timer = Timer(MAX_ENTRY_WAIT).start()
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_FINISH):
                raise AbyssShadowsFinished
            state = self.battle_entry_state()
            if state in ('prepare', 'prepare_loading', 'preset', 'battle', 'result'):
                return
            if timer.reached():
                self.request_takeover('challenge', f'no preparation or battle after {MAX_ENTRY_WAIT}s; state={state}')
            #
            if self.appear(self.I_ABYSS_ENEMY_FIRE):
                self.click(self.I_ABYSS_ENEMY_FIRE, interval=0.4)
                continue
            #
            if self.appear_then_click(self.I_ABYSS_FIRE, interval=1):
                continue
            # 挑战敌人后，如果是奖励次数上限，会出现确认框
            if self.appear_then_click(self.I_ENSURE_BUTTON, interval=1):
                continue
            #

    def start_abyss_shadows(self):
        # 尝试开启狭间暗域
        self.wait_until_appear(self.I_SELECT_DIFFICULTY, wait_time=2)
        if not self.appear(self.I_SELECT_DIFFICULTY):
            logger.info("Failed to Open abyss_shadows ,cause not found I_SELECT_DIFFICULTY")
            return
        if not self.appear(self.I_BTN_START):
            logger.info("Failed to Open abyss_shadows ,cause not found I_BTN_START")
            return
        # 选择难度
        self.ui_click(self.I_SELECT_DIFFICULTY, stop=self.I_DIFFICULTY_EASY, interval=2)

        difficulty_btn = None
        match self.config.model.abyss_shadows.abyss_shadows_time.difficulty:
            case AbyssShadowsDifficulty.EASY:
                difficulty_btn = self.I_DIFFICULTY_EASY
            case AbyssShadowsDifficulty.HARD:
                difficulty_btn = self.I_DIFFICULTY_HARD
            case AbyssShadowsDifficulty.NORMAL:
                difficulty_btn = self.I_DIFFICULTY_NORMAL
        self.ui_click_until_disappear(difficulty_btn, interval=2)
        # 开始
        self.ui_click(self.I_BTN_START, stop=self.I_START_ENSURE, interval=2)
        self.ui_click_until_disappear(self.I_START_ENSURE, interval=2)

    def process(self):
        while True:
            self.init_list_from_cfg()
            _next = self.get_next()
            if _next is None:
                break
            self.execute(_next)
            self.flash_list()

    def get_next(self) -> [Code, None]:
        # 获取下一个任务目标
        for ps in self.ps_list:
            if ps not in self.done_list and ps not in self.unavailable_list and ps not in self.failed_list:
                return ps

        if not self.config.model.abyss_shadows.abyss_shadows_time.try_complete_enemy_count:
            #
            logger.info("All done, don`t need to fix 246")
            return None

        # 已配置的已完成,若未打满奖励,尝试补全
        # 统计已完成的各类型数量
        done_counts = {
            EnemyType.BOSS: 0,
            EnemyType.GENERAL: 0,
            EnemyType.ELITE: 0
        }

        for code in self.done_list:
            enemy_type = code.get_enemy_type()
            done_counts[enemy_type] += 1

        need_boss = done_counts[EnemyType.BOSS] < self.min_count[EnemyType.BOSS]
        need_general = done_counts[EnemyType.GENERAL] < self.min_count[EnemyType.GENERAL]
        need_elite = done_counts[EnemyType.ELITE] < self.min_count[EnemyType.ELITE]

        logger.info(f"Need boss: {need_boss}, need general: {need_general}, need elite: {need_elite}")
        all_possible_codes = []
        for area in AreaType:
            area_code = IndexMap[area.name].value  # 如 DRAGON -> 'A'
            for num in ['1', '2', '3', '4', '5', '6']:
                all_possible_codes.append(Code(f"{area_code}-{num}"))

        for code in all_possible_codes:
            if code in self.done_list or code in self.unavailable_list or code in self.failed_list:
                continue

            enemy_type = code.get_enemy_type()

            if enemy_type == EnemyType.BOSS and need_boss:
                return code
            elif enemy_type == EnemyType.GENERAL and need_general:
                return code
            elif enemy_type == EnemyType.ELITE and need_elite:
                return code

        return None

    def open_navigation(self):
        while True:
            self.screenshot()
            if self.appear(self.I_CHECK_FINISH):
                raise AbyssShadowsFinished
            if self.appear(self.I_ABYSS_MAP):
                break
            if self.appear(self.I_ABYSS_NAVIGATION):
                self.click(self.I_ABYSS_NAVIGATION, interval=1)
                continue
            if self.appear(self.I_ABYSS_FIRE) or self.appear(self.I_ABYSS_GOTO_ENEMY):
                self.click(self.I_ABYSS_ENEMY_INFO_EXIT, interval=2)
                continue

    def execute(self, item_code: Code):
        area = item_code.get_areatype()

        if not self.change_area(area):
            return False
        # 当前应当在正确的区域
        #
        # if not self.check_available(item_code):
        #     return

        if not self.goto_enemy(item_code):
            # Failed navigation is not proof of death. Preserve it separately.
            self.failed_list.append(item_code)
            return False

        battle_count = MAX_BATTLE_COUNT
        while battle_count > 0:
            self.attack_enemy()
            # 战斗
            suc = self.run_battle(item_code)
            self.device.stuck_record_clear()
            if suc:
                self.done_list.append(item_code)
                logger.info(f'{item_code} completed its battle objective')
                return True
            battle_count -= 1
        self.failed_list.append(item_code)
        logger.warning(f'{item_code} exhausted {MAX_BATTLE_COUNT} attempts without confirmed completion')
        return False

    def run_battle(self, item_code: Code):
        """Complete one battle objective; never infer victory from elapsed time."""
        enemy_type = item_code.get_enemy_type()
        process = self.config.model.abyss_shadows.process_manage
        self.enter_battle(item_code)

        condition = process.generate_quit_condition(enemy_type)
        battle_timer = Timer(MAX_BATTLE_WAIT).start()
        confirmed_win = False
        self.device.screenshot_interval_set(1)
        self.device.stuck_record_add('BATTLE_STATUS_S')
        try:
            if process.is_need_mark_main(enemy_type):
                for _ in range(5):
                    self.screenshot()
                    if self.appear(self.I_MARK_MAIN):
                        break
                    self.click(self.C_MARK_MAIN, interval=1)
                    self.wait_until_appear(self.I_MARK_MAIN, wait_time=1)
            while True:
                self.screenshot()
                if battle_timer.reached():
                    self.request_takeover('battle', f'{item_code}: no settlement after {MAX_BATTLE_WAIT}s')
                if self.appear(self.I_FALSE):
                    logger.warning(f'{item_code}: defeat observed')
                    self.quit_battle()
                    return False
                if self.appear_then_click(self.I_WIN, interval=1):
                    confirmed_win = True
                    continue
                if self.appear_then_click(self.I_REWARD, interval=1):
                    confirmed_win = True
                    continue
                if self.appear(self.I_ABYSS_NAVIGATION):
                    logger.info(f'{item_code}: map returned, confirmed_win={confirmed_win}')
                    return confirmed_win
                if not confirmed_win:
                    damage = self.O_DAMAGE.ocr_digit(self.device.image) if condition.is_need_damage_value() else None
                    if condition.is_valid(damage):
                        logger.info(f'{item_code}: configured objective reached, leaving battle')
                        self.quit_battle()
                        return True
        finally:
            self.device.screenshot_interval_set()
            self.device.stuck_record_clear()

    def quit_battle(self):
        """Return to the map after a result or requested exit, with a bounded wait."""
        timer = Timer(30).start()
        while True:
            self.screenshot()
            if self.appear(self.I_ABYSS_NAVIGATION):
                return
            if timer.reached():
                self.request_takeover('battle-exit', 'no map confirmation after 30s')
            for button in (self.I_FALSE, self.I_EXIT_ENSURE, self.I_WIN, self.I_REWARD, self.I_EXIT):
                if self.appear_then_click(button, interval=1):
                    break

    def switch_preset_team_with_str(self, v: str):
        if not v:
            return
        tmp = v.split(',')
        if not tmp or len(tmp) != 2:
            logger.error(f"Due to a configuration error (value: {v}), an error occurred while switch preset team.")
            return
        self.switch_preset_team(True, int(tmp[0]), int(tmp[1]))

    def switch_soul_in_as(self):
        if self.switch_soul_done:
            return
        if not self.config.model.abyss_shadows.process_manage.enable_switch_soul_in_as:
            self.switch_soul_done = True
            return

        logger.info("start switch soul...")

        def switch_soul(_v: str):
            l = _v.split(',')
            if len(l) != 2:
                logger.error(f"Due to a configuration error (value: {_v}), an error occurred while switch soul.")
                raise RequestHumanTakeover
            self.run_switch_soul((int(l[0]), int(l[1])))

        self.ui_click_until_disappear(self.I_ABYSS_SHIKI, interval=2)
        process = self.config.model.abyss_shadows.process_manage
        soul_set = dict.fromkeys(v for v in (
            process.preset_boss, process.preset_general, process.preset_elite) if v)

        for v in soul_set:
            switch_soul(v)

        self.exit_abyss_records()
        self.switch_soul_done = True

    def check_available(self, item_code: Code):
        # 判断该怪物是否可用
        # TODO 设想使用平均亮度分辨 是否可用
        self.change_area(item_code.get_areatype())

        while True:
            if self.appear(self.I_ABYSS_NAVIGATION):
                self.click(self.I_ABYSS_NAVIGATION, interval=2)
                continue
            if self.appear(self.I_ABYSS_MAP):
                break

        return True

    def detect_area_status(self):
        # 在切换区域界面检查各个区域是否可用
        #
        available_areas = []
        unavailable_areas = []
        self.screenshot()
        for area in AreaType:
            if self.is_area_done(area):
                unavailable_areas.append(area)
                # self.unavailable_list += CodeList(IndexMap[area.name].value)
                logger.info(f"{area.name} unavailable")
                continue
            available_areas.append(area)
            logger.info(f"{area.name} available")
        return available_areas, unavailable_areas

    def is_area_done(self, area_type: AreaType):
        # 不再切换区域界面直接返回
        if not self.appear(self.I_ABYSS_DRAGON) and not self.appear(self.I_ABYSS_DRAGON_OVER):
            return False
        #
        res_img = self.device.image

        match area_type:
            case AreaType.DRAGON:
                ocr_res = self.O_DRAGON_DONE.ocr(res_img)
                return ocr_res.find('封印') != -1
            case AreaType.FOX:
                ocr_res = self.O_FOX_DONE.ocr(res_img)
                return ocr_res.find('封印') != -1
            case AreaType.LEOPARD:
                ocr_res = self.O_LEOPARD_DONE.ocr(res_img)
                return ocr_res.find('封印') != -1
            case AreaType.PEACOCK:
                ocr_res = self.O_PEACOCK_DONE.ocr(res_img)
                return ocr_res.find('封印') != -1

        return False

    def move_a_little(self):
        radius = 150
        # 寮里面摇杆的中心点
        p1 = (197, 568)
        import random
        dx, dy = random.randint(-radius, radius), random.randint(-radius, radius)
        self.device.swipe_adb(p1, (p1[0] + dx, p1[1] + dy), duration=0.5)
        logger.info(f"Swipe {p1} to {(p1[0] + dx, p1[1] + dy)}")


if __name__ == "__main__":
    raise SystemExit('Run the Abyss trial through the isolated OAS backend; see README.zh.md')
