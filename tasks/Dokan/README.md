# Dokan scheduling

[简体中文](README.zh.md)

Dokan uses the existing shared scheduler after the day's available rounds
finish or the day is skipped. For `scheduler.server_update` values other than
`09:00:00`, it schedules that clock `scheduler.delay_date` calendar days later,
plus one random delay from zero to `scheduler.float_time`. Set `delay_date` to
`1` for daily runs. The shared date helper retains its late-day jitter limit of
23:50. The existing `09:00:00` special case remains: completion uses the current
task's start time plus `success_interval` and random delay, rather than a fixed
09:00 start on the next day.

When `daily_attack_count` is `2` and the game reports one remaining attempt,
the next run is scheduled at the end of the current task plus
`scheduler.failure_interval`. This retry has no added random delay and is not
overridden by the daily clock. It is a separate task run; another running task
can delay its actual start. The interval must leave enough time for the second
round before the game's daily reset.

If the activity is not open, a check before the daily clock is rescheduled to
that exact clock. From the daily clock through two hours afterward, retries use
`failure_interval`; a later unsuccessful opening check schedules the next daily
run. The existing Monday–Thursday option and battle/remaining-attempt detection
still determine whether the task can run or a second round is available.

With `try_start_dokan` enabled, every eligible day attempts to create the guild's
Dokan before selecting an opponent, when the task reaches the selection scene
with attempts remaining. There is no Monday-only gate or once-per-day record;
another visit, including the second round, can attempt creation again. The
existing creation routine handles an already-created Dokan through its UI wait
and timeout behavior. With the Monday–Thursday option enabled, Friday through
Sunday still exit before reaching creation or combat.

## Example configuration

| Field | Value | Meaning |
| --- | --- | --- |
| `attack_count_config.daily_attack_count` | `2` | Attempt a second round when available |
| `scheduler.server_update` | `05:00:00` | Daily base time |
| `scheduler.delay_date` | `1` | Schedule the next calendar day after completion |
| `scheduler.float_time` | `00:30:00` | Add 0–30 minutes to the next daily start |
| `scheduler.failure_interval` | `00 00:10:00` | Wait 10 minutes before the second round or an opening retry |

With these values, a first round finishing at 05:20 schedules the second run
for 05:30. After the second round, the next daily run falls between 05:00 and
05:30 the next day. Times use the task process's clock.

Set the initial `scheduler.next_run` to the intended first start. Changing the
interval or daily clock does not recalculate a previously saved `next_run`, and
this scheduling method does not prevent an explicitly requested early run.

## Offline verification

Run `python -m unittest discover -s tests -p 'test_dokan_schedule.py'` from the
repository root. Tests execute the production Dokan scheduling method, task
wrapper, shared date helpers and scheduler with a controlled clock and in-memory
configuration. They cover both rounds, daily jitter bounds, the existing 09:00 special case,
opening retries, skipped days and single-round settings. They do not run an
emulator or verify game UI detection.
