# 第三方依赖声明（THIRD-PARTY NOTICES）

本软件包含以下第三方开源组件。各组件版权归其作者所有，按其许可证条款使用。
本文件与 LICENSE（GPLv3 全文）随安装包一起分发（位于 `_internal/` 目录），
最新版可于源码仓库根目录查阅。

## 直接依赖（随包分发）

| 组件 | 版本要求 | 许可证 | 说明 |
|---|---|---|---|
| PySide6（Qt for Python） | >=6.8.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | Qt Company。动态链接；分发二进制时须允许用户替换 Qt 库（本程序 PySide6 以独立 .pyd/.dll 形式位于安装目录 `_internal\PySide6\`，可直接替换），并随附本声明。Qt 源码：https://code.qt.io |
| numpy | >=1.26.0 | BSD-3-Clause | NumPy 开发者 |
| opencv-python-headless | >=4.10.0 | Apache-2.0 | OpenCV team |
| rapidocr-onnxruntime | >=1.3.24 | Apache-2.0 | RapidAI |
| onnxruntime | >=1.19.0 | MIT | Microsoft |
| Pillow | >=11.1.0 | MIT-CMU | Pillow 开发者 |
| pillow-heif | >=1.1.0 | BSD-3-Clause | pillow-heif 开发者 |
| rawpy | >=0.21.0 | MIT | LetMeLtd |
| exifread | >=3.0.0 | BSD-2-Clause | Gene Cash |
| piexif | >=1.1.3 | MIT | hMatoba（仅 tools/ 开发工具使用，不入安装包） |

## 随包分发的传递依赖

由 PyInstaller 依导入关系收集进安装包（上表的依赖链）。许可证均允许再分发，
本声明即其署名要求：

| 组件 | 许可证 | 引入来源 |
|---|---|---|
| shiboken6 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | PySide6 |
| PyYAML | MIT | rapidocr |
| pyclipper | MIT | rapidocr |
| Shapely | BSD-3-Clause | rapidocr |
| tqdm | MPL-2.0 AND MIT | rapidocr / onnxruntime |
| coloredlogs / humanfriendly | MIT | onnxruntime |
| flatbuffers | Apache-2.0 | onnxruntime |
| protobuf | BSD-3-Clause | onnxruntime |
| sympy / mpmath | BSD | onnxruntime |
| ml_dtypes | Apache-2.0 | onnxruntime |
| brotli | MIT | pillow-heif |
| six | MIT | 传递依赖 |
| packaging | Apache-2.0 OR BSD-2-Clause | 传递依赖 |
| typing_extensions | PSF-2.0 | 传递依赖 |

## 麒麟包（Linux aarch64）系统级组件

仅随 `PhotoManager-*-kylin-aarch64.tar.gz` 分发，均来自 Debian bullseye
aarch64 基础系统，以动态库形式位于 `_internal/` 与 `_internal/gstreamer-1.0/`，
可独立替换（LGPL 义务的履行方式同上）：

| 组件 | 许可证 | 说明 |
|---|---|---|
| GStreamer core/base/good/libav 插件 | LGPL-2.1+（libav 部分含 GPL 组件，按其原许可分发） | 多媒体播放后端，源码 https://gstreamer.freedesktop.org |
| glib 等系统库闭包 | LGPL-2.1+（个别为 BSD/MIT/X11） | 由 tools/arm/bundle_runtime_libs.py 递归收集（glibc 等基础运行时除外），源码 http://deb.debian.org/debian |

## fcitx5 输入法插件（仅麒麟包）

| 组件 | 许可证 | 说明 |
|---|---|---|
| libfcitx5platforminputcontextplugin.so | **BSD-3-Clause OR LGPL-2.1-or-later**（fcitx5-qt 5.1.16，KDE 双许可） | 以 BSD-3-Clause 选项分发。构建自上游源码 https://github.com/fcitx/fcitx5-qt （tag 5.1.16），构建脚本与参数随本仓库 `tools/arm/fcitx5-plugin/build.sh` 可复现；构建工具链为 conda-forge qt6-main 6.8.0（仅构建期使用） |

## 内置数据（非第三方依赖）

| 数据 | 来源 | 许可证 | 说明 |
|---|---|---|---|
| 繁简变体映射表（`photo_manager/core/zhvar.py`） | Unicode Unihan 数据库（`Unihan_Variants.txt`）+ 少量人工补充对 | **Unicode License**（允许再分发，需保留署名） | 0.5.59 起替代原 zhconv（GPLv2+，已移除）。数据由 `tools/gen_zhvar.py` 从 Unihan 生成，可复现；人工补充对为语言知识整理，未复制任何 GPL 数据。Unicode 许可证全文：https://www.unicode.org/license.txt |

## 随附 AI 模型

| 模型 | 来源 | 许可证 |
|---|---|---|
| Chinese-CLIP ViT-B/16（ONNX） | OFA-Sys / 优图实验室 | Apache-2.0（源码 https://github.com/OFA-Sys/Chinese-CLIP ，ONNX 由本仓库导出） |
| YuNet / SFace（ONNX） | OpenCV Zoo | Apache-2.0（已核对 opencv_zoo 仓库 LICENSE）；随本仓库分发，源码 https://github.com/opencv/opencv_zoo |

## 待办

- [ ] CLA 签署记录积累到一定量后，整理 `docs/CLA-SIGNATURES.md`

## 本项目许可

本项目以 **GPLv3** 发布（LICENSE 文件为 FSF 官方全文），并采用 GPLv3 + 商业授权
双重授权模式（见 COMMERCIAL-LICENSE.md）。贡献者版权经 CLA.md 转让给版权持有人。
各源文件头含 SPDX 标识与版权声明；数据生成脚本 tools/gen_zhvar.py 可从
Unicode Unihan 数据库复现繁简变体表。
