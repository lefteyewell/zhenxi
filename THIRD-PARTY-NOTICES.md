# 第三方依赖声明（THIRD-PARTY NOTICES）

本软件包含以下第三方开源组件。各组件版权归其作者所有，按其许可证条款使用。

| 组件 | 版本要求 | 许可证 | 说明 |
|---|---|---|---|
| PySide6（Qt for Python） | >=6.9.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0 | Qt Company。动态链接；分发二进制时须允许用户替换 Qt 库（本程序 PySide6 以独立 .pyd/.dll 形式位于安装目录 `_internal\PySide6\`，可直接替换），并随附本声明。Qt 源码：https://code.qt.io |
| numpy | >=1.26.0 | BSD-3-Clause | NumPy 开发者 |
| opencv-python-headless | >=4.10.0 | Apache-2.0 | OpenCV team |
| rapidocr-onnxruntime | >=1.3.24 | Apache-2.0 | RapidAI |
| onnxruntime | >=1.19.0 | MIT | Microsoft |
| Pillow | >=11.1.0 | MIT-CMU | Pillow 开发者 |
| pillow-heif | >=1.1.0 | BSD-3-Clause | pillow-heif 开发者 |
| rawpy | >=0.21.0 | MIT | LetMeLtd |
| exifread | >=3.0.0 | BSD-2-Clause | Gene Cash |
| piexif | >=1.1.3 | MIT | hMatoba（仅 tools/ 开发工具使用） |

## 内置数据（非第三方依赖）

| 数据 | 来源 | 许可证 | 说明 |
|---|---|---|---|
| 繁简变体映射表（`photo_manager/core/zhvar.py`） | Unicode Unihan 数据库（`Unihan_Variants.txt`）+ 少量人工补充对 | **Unicode License**（允许再分发，需保留署名） | 0.5.59 起替代原 zhconv（GPLv2+，已移除）。数据由 `tools/gen_zhvar.py` 从 Unihan 生成，可复现；人工补充对为语言知识整理，未复制任何 GPL 数据。Unicode 许可证全文：https://www.unicode.org/license.txt |

## 随附 AI 模型

| 模型 | 来源 | 许可证 |
|---|---|---|
| Chinese-CLIP ViT-B/16（ONNX） | OFA-Sys / 优图实验室 | 见模型卡（随模型附带 config.json） |
| YuNet / SFace（ONNX） | OpenCV Zoo | Apache-2.0（已核对 opencv_zoo 仓库 LICENSE）；随本仓库分发，源码 https://github.com/opencv/opencv_zoo |

## 待办

- [ ] CLA 签署记录积累到一定量后，整理 `docs/CLA-SIGNATURES.md`

## 本项目许可

本项目以 **GPLv3** 发布（LICENSE 文件为 FSF 官方全文），并采用 GPLv3 + 商业授权
双重授权模式（见 COMMERCIAL-LICENSE.md）。贡献者版权经 CLA.md 转让给版权持有人。
各源文件头含 SPDX 标识与版权声明；数据生成脚本 tools/gen_zhvar.py 可从
Unicode Unihan 数据库复现繁简变体表。
