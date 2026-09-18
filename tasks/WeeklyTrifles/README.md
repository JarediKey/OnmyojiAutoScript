# Weekly trifles

[简体中文](README.zh.md)

Area Boss sharing attempts to open the sharing selector at most three times,
with a minimum 3-second interval. It gives the final click another 3 seconds to
produce the selector before skipping. The selector is checked before the retry
limit, so a successful third attempt continues normally. Once a share click has
been made, the task does not keep clicking challenge-list coordinates underneath.
The daily-battle tab and challenge-record entry are each capped at three clicks,
and the full entry phase has a 30-second deadline.

On entry failure, the task logs that sharing was skipped and that its reward is
unconfirmed, returns to a recognized Area Boss/exploration/courtyard page, and
continues the remaining enabled weekly steps. It does not restart the game solely
because the share selector failed to open. Recovery clicks are spaced 3 seconds
apart per button. If no safe return page is recognized within 20 seconds, normal
stuck recovery applies instead of continuing on an unknown page.

The existing WeChat/QR/reward flow after the selector appears, other share tasks,
and weekly scheduling remain unchanged. A skipped share is not retried separately
until the next scheduled or manual WeeklyTrifles run. No external sharing is
performed by the regression tests.

Offline checks: `python -m unittest discover -s tests -p test_weekly_area_share.py -v`.
Live game behavior has not been verified.
