# Battle wait options

[简体中文](README.zh.md)

Battle wait uses the upstream typed runtime: `battle_wait_strategy` selects hooks,
and `battle_wait_options` supplies event option dataclasses. Options combine typed
defaults, decorator overrides, and active context overrides in that order. An
override replaces the entire event option object; omitted fields use its defaults,
including reward click exclusions. Nested contexts restore their enclosing context.
Decorated calls restore the options active at call time, including on exceptions,
so temporary settings do not leak into later tasks. The old `with_options()` API
is replaced by `with battle_wait_options(...)`.

Hooks receive shared `pub` and hook-specific `pri` contexts. Task state resets
when the owner changes; battle state resets for each decorated battle call.
Completion returns `True` only when `pub.per_battle.success` is
`BattleResult.SUCCESS`; completion alone does not imply victory. The failure hook
records `BattleResult.FAILURE` before enabling completion.

## Post-battle statistics exclusions

The shared post-battle random click generator always excludes both statistics
entries: the top-left reward-page button `(44,32,72,72)` and the victory-page
button `(383,559,52,49)`. Rectangles use `(x,y,width,height)` with the origin at
the upper left. The second region reuses `C_END_SOUL_DETAILS`.

These exclusions apply to the first victory click, later reward clicks and
completion fallback clicks, including empty or task-specific exclusion lists.
They do not change the initial click on the recognized victory banner.

Regression checks: `python -m pytest tests/tasks/Component/GeneralBattle`.
These are offline checks, not game validation.
