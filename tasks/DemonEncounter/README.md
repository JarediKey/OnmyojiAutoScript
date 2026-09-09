# Demon Encounter

[简体中文](README.zh.md)

In **Demon Encounter → Demon Encounter options**, enable **Skip all battles**
to complete the four discoveries, collect discovery rewards, and process quizzes
and treasure boxes without fighting. Monster/small-boss lanterns, realm battles,
large-boss lanterns, the daily boss, and pre-battle soul switching are skipped.
Treasure boxes still follow the existing purchase rules, including the default
mystery-amulet purchase; this option does not disable purchases. Mystery tasks
remain unhandled as in the full workflow.

The task returns to the courtyard and uses its existing next-run scheduling.
Battle rewards are not earned in this mode. The option defaults to **off** for
each account, preserving the full workflow. Merely adding the option does not
enable the task or alter an account's schedule.

OASX retrieves additional translations when its navigation controller initializes.
If the new label or help text is missing after a backend update, restart OASX
so it reloads the task schema and translations.

In the full workflow, a recognized zero remaining daily challenge count ends
the task early. This check does not apply to **Skip all battles**, so discoveries
and non-combat events remain available after the daily battle is complete.
