# OCR 颜色过滤

[English](README.md)

OCR 源 JSON 和 `RuleOcr` 的 `method` 支持以下字符串：

| 方法 | 行为 |
|---|---|
| `Default` | 保持既有行为，原样传递图像。 |
| `CF_RGB(CCCCCC,FFFFFF)` | 保留 RGB 各通道均在 204～255 范围内的像素，包含边界。 |
| `CF_HSV(0980B4,1ED2FF)` | 保留 HSV 值满足 H=9～30、S=128～210、V=180～255 的像素。 |

每个边界由三个十六进制字节组成。方法名与十六进制数字不区分大小写，允许外围
空白。范围包含边界，各通道下界不得超过上界。OpenCV 的 uint8 HSV 中 H 为
0～179（`00`～`B3`），S/V 为 0～255，不支持色相跨零的范围。规则构造时遇到
格式错误会抛出 `ValueError`，不会悄悄关闭过滤。

颜色过滤要求 uint8 三通道 **RGB** 图像，将范围外像素置黑，并保留范围内像素
原始 RGB 值、图像尺寸及数据类型，不修改原始截图。HSV 筛选不会将保留像素做
HSV 往返转换。`Default`、`OcrMethod.DEFAULT` 及从 `module.ocr.base_ocr`
导入该枚举的方式继续有效。

过滤在 `BaseCor.pre_process` 中执行，位于单行识别和检测推理之前，适用于本地
模型与既有 OCR 代理。OCR 服务协议、后处理与坐标逻辑不变。任务自定义的
`pre_process` 覆盖仍优先；如果也要应用配置的颜色过滤，可调用
`super().pre_process(image)`。

修改 OCR 源 JSON 后通过 `dev_tools/assets_extract.py` 重新生成 `assets.py`，
不要手改生成的资源声明。浏览器标注工具的文本 `method` 字段可直接填写上述表达式。
旧 QML 规则编辑器仍只提供 `Default`，未新增颜色范围
编辑控件；使用该编辑器时，自定义方法仍需在源 JSON 中维护。

运行隔离回归测试：

```sh
python -m unittest discover -s tests -p 'test_ocr_color_filter.py' -v
```

测试使用真实 NumPy/OpenCV 像素，在 OCR 接入检查中替代模型／服务加载，不下载
模型权重或连接设备。它不能证明当前狭间 UI 的识别准确率；将旧颜色边界用于生产前，
需使用新的 1280×720 截图验证。

参考：[OpenCV inRange 教程](https://docs.opencv.org/4.x/da/d97/tutorial_threshold_inRange.html)。
