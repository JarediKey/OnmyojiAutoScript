# Battle wait options

[简体中文](README.zh.md)

Battle wait options combine global defaults, decorator options, and active context
options, in that precedence order. Overrides replace an entire event dictionary.
`with_options()` returns an independent context; exiting restores the previous
context and preserves the decorator's options. This retains the upstream reward
click exclusions while preventing temporary task options from leaking into later
calls. Nested contexts restore their enclosing context.
