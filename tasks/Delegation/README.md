# Delegation

[简体中文](README.zh.md)

Completed tasks are located by their completion ribbons. The script clicks the
portrait 25 pixels below the bottom of the OCR ribbon, because the ribbon itself
is not interactive. If several tasks are complete, the topmost match is selected
without combining their coordinates.

Reward collection retains the existing settlement and dialogue handling. Card
entry is retried at three-second intervals, at most three times. An unresponsive
entry or 20 seconds without a recognized reward action requests human takeover
instead of restarting the game. Disappearance of a ribbon alone is not treated
as successful collection. Task selection and scheduling are unchanged.

Run offline checks with `python -m unittest discover -s tests -p test_delegation_rewards.py`.
The incident screenshot validates the target geometry; actual game navigation
and reward collection require a manual run after deployment.
