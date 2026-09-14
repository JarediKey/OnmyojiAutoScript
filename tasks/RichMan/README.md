# Rich Man shop recognition and navigation

[简体中文](README.zh.md)

Product-list icons in Honor, Charisma, Bondlings, Friendship, Scales, Special,
Medal, and Consignment use a 0.7 matching threshold (27 rules). Purchase
confirmations and scroll-end markers retain their existing thresholds. The
sold-out mystery-amulet icon in the account-3 incident scores approximately 0.72
and is recognized with this threshold. Icon detection is not purchase confirmation.

## Ordered category navigation

The five primary categories are Special → Duel → Friendship → Medal → Charisma.
Duel's permanent/seasonal children are not counted as primary categories. All five
entry methods share one helper; there is no detour through Special.

Each fresh screenshot identifies visible category labels throughout the right
sidebar. The selected category is identified by associating a primary-tab highlight
with a visible label. The top resource icons are not used as selection evidence.
Missing or ambiguous highlight evidence yields an unknown selection. An already
selected target must stay selected for at least one second across multiple frames
before navigation completes.

A visible target is clicked directly without scrolling. A target earlier than all
visible categories triggers a **downward finger swipe** to reveal earlier entries;
a target later than all visible categories triggers an **upward finger swipe** to
reveal lower entries. Each swipe uses the existing `RuleSwipe`/`swipe()` stack and
is followed by a one-second settling wait and a fresh screenshot. If no labels are
recognized, or the missing target is between visible labels, direction is ambiguous
and no swipe is made. After a target click, the helper waits for selection instead
of scrolling the transitioning panel.

The helper allows at most three swipes and three target clicks (at least three
seconds apart), with a 25-second navigation deadline after entering the sundry
shop. Failure raises `GameStuckError` instead of buying from an unconfirmed category.
Product-list scrolling, purchase options, and shop-return behavior are unchanged.

Offline checks: `python -m unittest discover -s tests -p test_shop_category_navigation.py -v`
(requires OpenCV). Captured screenshots confirm Duel selection and visible labels;
simulated states cover both directions, retries, and confirmation. The shifted
sidebar image check is synthetic, not a real swipe recording. Other selected-tab
appearances and actual sidebar gestures still need live validation.

## Shop return

Rich Man and Mystery Shop share `MallNavbar.back_mall()` for final shop cleanup.
It takes a fresh screenshot and checks the mall and courtyard before each possible
return click. Either page completes cleanup without another click, and the detected
page becomes `ui_current`. Courtyard detection uses the shared page matcher,
including the configured courtyard skin.

While neither destination is visible, it clicks a recognized yellow-back button
at least 3 seconds apart. If neither page is recognized within the 20-second wait
window, it raises `GameStuckError` for the existing recovery flow; the task does not
report success. Other return actions and purchase settings are unchanged.

Offline regression checks: `python -m unittest discover -s tests -p test_mall_return.py -v`.
These cover return transitions, click spacing, and timeout behavior. The corrected
completion logic has not been live-tested in the game.
