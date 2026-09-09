"""Read the OS timezone without inheriting the scheduler's TZ override."""
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.responses import JSONResponse


READ_FAILED = 'SYSTEM_TIMEZONE_READ_FAILED'
MAPPING_FAILED = 'SYSTEM_TIMEZONE_MAPPING_FAILED'
UNSUPPORTED = 'SYSTEM_TIMEZONE_UNSUPPORTED_PLATFORM'
MESSAGES = {
    READ_FAILED: 'Unable to read system timezone.',
    MAPPING_FAILED: 'Unable to map system timezone to an IANA identifier.',
    UNSUPPORTED: 'System timezone detection is not supported on this platform.',
}

# A fresh interpreter avoids tzlocal's cache and the server's process-wide TZ.
# Do not import server.py in the probe: it changes the process timezone.
PROBE = '''
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
try:
    from tzlocal import get_localzone_name
    name = get_localzone_name()
    if not name:
        raise LookupError('No system timezone name')
    ZoneInfo(name)
    result = {'timezone': name}
except ZoneInfoNotFoundError:
    result = {'code': 'SYSTEM_TIMEZONE_MAPPING_FAILED'}
except Exception:
    result = {'code': 'SYSTEM_TIMEZONE_READ_FAILED'}
print(json.dumps(result), flush=True)
'''


class SystemTimezoneResponse(BaseModel):
    timezone: str


class SystemTimezoneError(BaseModel):
    code: Literal[
        'SYSTEM_TIMEZONE_READ_FAILED',
        'SYSTEM_TIMEZONE_MAPPING_FAILED',
        'SYSTEM_TIMEZONE_UNSUPPORTED_PLATFORM',
    ]
    message: str


def read_system_timezone() -> dict:
    """Read once per call; never change environment or clock in this process."""
    if sys.platform not in ('win32', 'linux', 'darwin'):
        return {'code': UNSUPPORTED}
    env = os.environ.copy()
    env.pop('TZ', None)
    executable = Path(sys.executable)
    if sys.platform == 'win32' and executable.name.lower() == 'pythonw.exe':
        # pythonw has no reliable standard streams; use the same bundled runtime.
        executable = executable.with_name('python.exe')
    try:
        process = subprocess.run(
            [str(executable), '-c', PROBE],
            env=env, capture_output=True, encoding='utf-8', timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            check=True,
        )
        result = json.loads(process.stdout)
        if isinstance(result, dict):
            if isinstance(result.get('timezone'), str) and result['timezone']:
                return {'timezone': result['timezone']}
            if result.get('code') in (READ_FAILED, MAPPING_FAILED):
                return {'code': result['code']}
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return {'code': READ_FAILED}


system_timezone_app = APIRouter()


@system_timezone_app.get(
    '/system_timezone',
    response_model=SystemTimezoneResponse,
    responses={
        500: {'model': SystemTimezoneError, 'description': 'System timezone read or mapping failed.'},
        501: {'model': SystemTimezoneError, 'description': 'Unsupported operating system.'},
    },
    summary='Read the operating system timezone as an IANA identifier',
    description='Read-only. Re-read on every request; ignores the OAS process TZ override. No request parameters.',
)
def system_timezone():
    result = read_system_timezone()
    code = result.get('code')
    if code:
        return JSONResponse(
            status_code=501 if code == UNSUPPORTED else 500,
            content={'code': code, 'message': MESSAGES[code]},
            headers={'Cache-Control': 'no-store'},
        )
    return JSONResponse(content=result, headers={'Cache-Control': 'no-store'})
