# WantedQuests

[English](README.md)

每场秘闻战斗结束后，先推进已识别的剧情对话，再返回导航。只有识别到剧情姓名底板才点击，并等待其稳定消失；处理上限为 30 秒，未结束时抛出 GameStuckError。该处理不会点击其他战斗或无法识别的页面。

恢复逻辑检查：`python -m unittest discover -s tests -p test_login_and_secret_recovery.py -v`。离线检查不能代替游戏实测。
