# Gold Youkai room waiting

[简体中文](README.zh.md)

After creating each public room, wait for all four teammate slots to fill (five
players including the leader). Reuse the four existing empty-slot templates; all
must be absent, the room and challenge button visible, and fullness stable for
at least two seconds across three screenshots before starting early.

If the room is not full after 180 seconds, challenge with the current players.
The game's own countdown can start the battle earlier; a recognized preparation
or battle screen is accepted without another click. Room waiting uses the existing
long-wait marker so the ordinary 60-second inactivity check does not interrupt it.

Challenge clicks are two seconds apart and must reach a preparation/battle screen
within 15 seconds. A missed room detection alone is not treated as battle entry.
Unconfirmed entry follows the existing stuck-game recovery. This policy applies
only to Gold Youkai; Experience Youkai and other invitation tasks are unchanged.

Checks: `python -m pytest tests/test_gold_youkai_room_wait.py`.
