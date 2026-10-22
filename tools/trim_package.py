#!/usr/bin/env python
# PhotoManager - 照片管理系统
# Copyright (C) 2026 蒙汗药
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""打包后瘦身（trim）：删除 PyInstaller collect_all 多收、但本程序不用的 Qt 组件。

用法：
    python tools/trim_package.py [dist/PhotoManager]

删除项（均经源码核对：本程序零引用）：
  1. Qt WebEngine 全套（332M）：dll + WebEngineProcess + resources/*.pak +
     qml/QtWebEngine|QtWebView + 相关 metatypes —— 本程序无任何网页浏览功能；
  2. Qt 官方翻译 305 个 .qm（60M）：界面文案全为 QML 硬编码中文，不走 tr()；
     将来的多语言版用应用自己的 .qm，与此无关；
  3. 未使用的 QML 模块（Qt3D/Charts/Quick3D/DataVisualization/Location/... 约 7M）：
     QML 只 import QtQuick / QtQuick.Controls / QtQuick.Layouts /
     QtQuick.Window / QtMultimedia；
  4. PySide6 doc/include/glue 开发文件（约 1.7M）。

明确不动：models/（CLIP 726M 是核心功能）、cv2、onnxruntime、rapidocr、
PIL、libheif、Qt6Core/Gui/Qml/Quick/Widgets/Multimedia/Network 等运行时组件。

典型效果：1.7G → 约 1.3G。删完必须冒烟（起 exe 验证）。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

# 未使用的 QML 模块（保留：Qt / QtCore / QtQml / QtQuick / QtMultimedia）
_UNUSED_QML = [
    "Qt3D", "Qt5Compat", "QtCharts", "QtDataVisualization", "QtGraphs",
    "QtLocation", "QtNetwork", "QtPositioning", "QtQuick3D",
    "QtRemoteObjects", "QtScxml", "QtSensors", "QtTextToSpeech",
    "QtWebChannel", "QtWebEngine", "QtWebView",
]


def _rm(path: Path) -> int:
    """删除文件/目录，返回释放字节数（不存在返回 0）。"""
    if not path.exists():
        return 0
    size = path.stat().st_size if path.is_file() else sum(
        f.stat().st_size for f in path.rglob("*") if f.is_file())
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as e:
        print(f"  [跳过] {path.name}: {e}")
        return 0
    return size


def trim(dist: Path) -> tuple[int, int]:
    exe = dist / "PhotoManager.exe"
    if not exe.exists():
        raise SystemExit(f"未找到 {exe}——请确认这是打包目录")
    internal = dist / "_internal"
    pyside = internal / "PySide6"
    before = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
    freed = 0

    # 1) WebEngine 全套
    for pat in ("Qt6WebEngine*.dll", "Qt6WebEngineProcess.exe",
                "qtwebengine*.pak", "qtwebenginecore_metatypes.json",
                "qt6webengine*_metatypes.json"):
        for f in pyside.rglob(pat):
            freed += _rm(f)
    # 2) Qt 官方翻译
    trans = pyside / "translations"
    if trans.is_dir():
        for qm in trans.glob("*.qm"):
            freed += _rm(qm)
        # 空目录一并清掉
        try:
            trans.rmdir()
        except OSError:
            pass
    # 3) 未使用的 QML 模块
    qml = pyside / "qml"
    if qml.is_dir():
        for name in _UNUSED_QML:
            freed += _rm(qml / name)
    # 4) PySide6 开发文件（doc/include/glue）
    for name in ("doc", "include", "glue"):
        freed += _rm(pyside / name)

    after = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
    return before, after


def main() -> int:
    dist = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist/PhotoManager")
    if not dist.is_dir():
        raise SystemExit(f"目录不存在: {dist}")
    before, after = trim(dist)
    print(f"trim 前: {before / 1024 ** 3:.2f} GB")
    print(f"trim 后: {after / 1024 ** 3:.2f} GB")
    print(f"节省:   {(before - after) / 1024 ** 3:.2f} GB")
    print("请务必冒烟验证：QT_QPA_PLATFORM=offscreen ./PhotoManager.exe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
