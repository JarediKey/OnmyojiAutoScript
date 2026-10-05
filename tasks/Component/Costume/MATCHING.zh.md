# 皮肤匹配

[English](MATCHING.md)

替换皮肤时原地更新图片规则，保留导航持有的对象引用；清除图片及特征缓存，
应用新模板的匹配方法。之前加载的模板不得继续用于新皮肤。
`rp_roi_back=False` 时保留固定搜索区域。

回归检查：`python -m pytest tests/test_skin_template_reload.py`。
