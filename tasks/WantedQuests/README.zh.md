# WantedQuests

[English](README.md)

每场秘闻战斗结束后，先推进已识别的剧情对话，再返回导航。旧剧情特征或新增的山兔姓名栏模板均可触发点击，间隔为 1.5 秒。识别到剧情时优先推进，不会因为背景中同时出现目标标志就退出。只有挑战按钮或秘闻列表在多张截图中持续出现至少 1 秒，才确认结束；仅仅匹配不到剧情不代表完成。

未知画面不点击，并重新计时确认目标页面。剧情处理上限为 30 秒，无法确认目标页面时抛出 `GameStuckError`，进入原有恢复流程。等待下一场挑战的上限为 10 秒，完成战斗后返回秘闻列表的上限为 20 秒，不会将未完成任务记录为成功。

新模板已用三次山兔剧情故障画面及一张庭院负样本验证。回归素材仅保留裁剪后的界面区域。其他仍无法识别的剧情页需要额外证据或模板，尚未进行游戏实机回放。

恢复逻辑检查：`python -m unittest discover -s tests -p test_login_and_secret_recovery.py -v`。模板检查：`python -m unittest discover -s tests -p test_wanted_story_assets.py -v`（需要 OpenCV）。离线检查不能代替游戏实测。
