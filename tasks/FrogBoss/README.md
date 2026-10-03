# FrogBoss upstream implementation

[简体中文](README.zh.md)

This implementation uses FrogBoss from upstream dev `c1dc5059`, including
PR #1850 (`670f194a`). The custom amount-border prototype and local loss-transition
implementation are retired; generated assets retain upstream rule values.

Betting handles the reward-information overlay before background controls, selects
the upper part of the matched 300000-coin bag once, and submits at most three times
three seconds apart. The flow has a 20-second deadline and accepts already-bet or
rest states. Selection is tracked by the successful selection call, not by a
separate selected-border image.

The optional Oas strategy reads visible game-history rows twice without scrolling.
Stable date/round, selected-side and win/loss observations can settle a unique saved
decision; ambiguous or conflicting records stay unverified. Verified source weights
are historical correctness minus 0.5; new sources are neutral. Before any verified
result, expert-majority and crowd-majority opinions each contribute one vote.

Private history remains under `data/frog_oas/<instance>.jsonl`. Account strategy
settings are preserved. Network prediction calls and game bets are not exercised
by offline tests. Run: `python -m pytest tasks/FrogBoss/test_frog_oas.py tasks/FrogBoss/test_betting_flow.py`.
Live recognition and betting still require game validation.
