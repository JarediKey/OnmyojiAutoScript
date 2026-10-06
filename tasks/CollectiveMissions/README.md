# Collective mission donation rewards

[简体中文](README.zh.md)

Material donations and N-card feeding submit the selected offering and drain
reward overlays without assuming a fixed popup count. Reward visibility is
checked separately from click cooldown, before checking the mission list.

Completion requires at least one reward click, no visible submit button or
reward overlay, and the mission-records indicator remaining visible for three
seconds across multiple frames. Another reward or an unknown page resets this
stability check. After the first reward click, the handler does not submit again.
A 20-second deadline raises GameStuckError if completion cannot be verified.

This supports one, two, or more reward overlays within the observation window.
A reward arriving after the three-second stable-list window is not covered.
The donation amount, mission selection, and other mission-card reward handling
are unchanged.

## Soul selection

A zero submission count means no selection yet. The first soul's level marker
(the existing OCR keyword `古` for `+0`) is positive evidence of an item, not a
reason to exit. While it is visible, attempt at most three 1.5-second long presses
with the existing 2.5-second click interval, checking a fresh screenshot after each.
A positive submission count proceeds to submission. Missing level text must persist
for at least one second across three frames; unreadable counts are not treated as
zero. Selection has a 15-second deadline.

Unconfirmed selection saves a private screenshot, leaves the submission panel,
and schedules an unsuccessful retry ten minutes later, overriding the daily clock
for this retry only. It does not mark a zero-submission run successful. Selection
and reward processing for other mission types are unchanged.

Run offline checks from the repository root:

```sh
python -m unittest discover -s tests -p test_collective_donation_rewards.py -v
```

These deterministic checks simulate UI frames and time; they are not live
verification of the game's reward timing.
