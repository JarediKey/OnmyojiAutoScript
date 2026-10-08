"""Pure notification and recovery scheduling decisions."""
from datetime import datetime, timedelta
import re

GAP = timedelta(minutes=30)
TERMINAL = ('RequestHumanTakeover', 'ScriptError', 'Exception occured', '任务连续失败三次')


def terminal_profile(payload, names):
    content = str(payload.get('content', ''))
    if not any(marker in content for marker in TERMINAL):
        return None
    for name in names:
        if '<' + name + '>' in content or str(payload.get('title', '')).startswith(name + ' '):
            return name
    return None


def enabled_tasks(config):
    return sorted((datetime.fromisoformat(v['scheduler']['next_run']), key)
                  for key, v in config.items() if isinstance(v, dict)
                  and v.get('scheduler', {}).get('enable')
                  and v['scheduler'].get('next_run'))


def plan_recovery(configs, failed, now):
    """Pack unfinished failed profiles first, then shift only colliding batches.

    Same-profile tasks within 30 minutes form a batch and keep their offsets.
    Stop considering later batches when the collision chain ends.
    """
    changes = []
    batches = []
    slots = []
    cursor = now
    for name in failed:
        overdue = [(t, k) for t, k in enabled_tasks(configs[name]) if t <= now]
        if overdue:
            slots.append((name, cursor))
            for _, key in overdue:
                changes.append((name, key, cursor))
            cursor += GAP
    if not slots:
        return [], []
    for name, config in configs.items():
        remaining = [(t, k) for t, k in enabled_tasks(config)
                     if not (name in failed and t <= now)]
        for stamp, key in remaining:
            if batches and batches[-1][0] == name and stamp - batches[-1][1] < GAP:
                batches[-1][2].append((stamp, key))
            else:
                batches.append([name, stamp, [(stamp, key)]])
    batches.sort(key=lambda b: b[1])
    last_name, last_start = slots[-1]
    for name, original, tasks in batches:
        if original >= last_start + GAP:
            break
        target = max(original, last_start if name == last_name else last_start + GAP)
        shift = target - original
        for stamp, key in tasks:
            if shift:
                changes.append((name, key, stamp + shift))
        slots.append((name, target))
        last_name, last_start = name, target
    return changes, slots


def emulator_identity(device):
    match = re.fullmatch(r'MuMuPlayer-(12\.0|15\.0)-(\d+)', device['emulatorinfo_name'])
    if not match:
        raise ValueError('Unsupported emulator identity')
    version, index = match.groups()
    expected = '127.0.0.1:' + str(16384 + 32 * int(index))
    if device['serial'] != expected:
        raise ValueError('Emulator identity and ADB serial disagree')
    return version.split('.')[0], int(index)
