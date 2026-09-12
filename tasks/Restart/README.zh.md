# Restart

[English](README.md)

收取邮件优先使用庭院右上方的固定信封入口，再尝试移动的小纸人入口。邮件入口最多等待 12 秒，每轮收获只尝试一次。进入失败后继续登录流程，邮件留待下次登录收取。奖励收取配置不变。

恢复逻辑检查：`python -m unittest discover -s tests -p test_login_and_secret_recovery.py -v`。离线检查不能代替游戏实测。
