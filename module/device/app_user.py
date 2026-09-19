"""Select one Android user's game without changing the foreground OS user."""

import re
import shlex
import time

from module.exception import RequestHumanTakeover
from module.logger import logger


class AndroidUserApp:
    _started_app_user = None

    def ensure_app_user(self):
        """Prepare the selected clone before the first task can interact with it."""
        user_id = self.config.script.device.user_id
        if user_id >= 0 and self._started_app_user != (user_id, self.package):
            self.app_start()

    def _app_user_command(self, command, timeout=10):
        """Require both a successful shell exit and no Android command error."""
        command = shlex.join(str(arg) for arg in command)
        output = self.adb_shell(
            command + '; printf "\\nOAS_APP_EXIT:%s\\n" "$?"', timeout=timeout)
        output = output.replace('\r\n', '\n')
        body, marker, status = output.rpartition('\nOAS_APP_EXIT:')
        if (not marker or status.strip() != '0'
                or re.search(r'(?im)^\s*(?:Error:|Exception|Security exception:)', body)):
            raise RequestHumanTakeover(f'Android user command failed: {command}\n{output}')
        return body.strip()

    def app_current_user(self):
        """Read the resumed activity's user, rather than the desktop's OS user."""
        output = self._app_user_command(['dumpsys', 'activity', 'activities'])
        activities = re.findall(
            r'^\s*(?:topResumedActivity|mResumedActivity)\s*[:=]\s*ActivityRecord\{'
            r'\S+\s+u(\d+)\s+([^\s/]+)/', output, re.MULTILINE)
        identities = {(int(user), package) for user, package in activities}
        if len(identities) == 1:
            return identities.pop()
        return None

    def app_start_user(self):
        """Validate the target, stop other copies, and verify the selected clone."""
        self._started_app_user = None
        user_id = self.config.script.device.user_id
        users_output = self._app_user_command(['pm', 'list', 'users'])
        users = sorted({int(value) for value in re.findall(r'UserInfo\{(\d+):', users_output)})
        if user_id not in users:
            raise RequestHumanTakeover(f'Android user {user_id} does not exist on {self.serial}')

        # Finish all read-only checks before stopping any copy of the game.
        installed_users = []
        for other_user in users:
            packages = self._app_user_command([
                'pm', 'list', 'packages', '--user', other_user, self.package])
            if self.package in re.findall(r'^package:([^\s]+)$', packages, re.MULTILINE):
                installed_users.append(other_user)
        if user_id not in installed_users:
            raise RequestHumanTakeover(f'{self.package} is not installed for Android user {user_id}')

        resolved = self._app_user_command([
            'cmd', 'package', 'resolve-activity', '--brief', '--user', user_id,
            '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.LAUNCHER',
            self.package])
        components = re.findall(r'^' + re.escape(self.package) + r'/[\w.$]+$', resolved, re.MULTILINE)
        if len(components) != 1:
            raise RequestHumanTakeover(f'Cannot resolve {self.package} launcher for Android user {user_id}')

        # MuMu clone profiles may be stopped even while the emulator is running.
        self._app_user_command(['am', 'start-user', '-w', user_id], timeout=30)
        for other_user in installed_users:
            if other_user != user_id:
                logger.info(f'Stop other game copy: {self.package}, Android user {other_user}')
                self._app_user_command(['am', 'force-stop', '--user', other_user, self.package])

        logger.info(f'Start selected game: {self.package}, Android user {user_id}')
        self._app_user_command([
            'am', 'start', '--user', user_id, '-a', 'android.intent.action.MAIN',
            '-c', 'android.intent.category.LAUNCHER', '-n', components[0]], timeout=30)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.app_current_user() == (user_id, self.package):
                self._started_app_user = (user_id, self.package)
                logger.info(f'Confirmed game foreground: {self.package}, Android user {user_id}')
                return
            time.sleep(0.5)
        raise RequestHumanTakeover(f'{self.package} did not reach the foreground as Android user {user_id}')

    def app_stop_user(self):
        """Stop only the configured user's copy during restart or shutdown."""
        self._app_user_command([
            'am', 'force-stop', '--user', self.config.script.device.user_id, self.package])
        self._started_app_user = None
