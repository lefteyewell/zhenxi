# -*- coding: utf-8 -*-
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
"""打包后体积裁剪：删除 PyInstaller hook 收集的 Qt WebEngine / 开发资源 / 多余翻译。

支持 Windows（PySide6 顶层 dll）与 Linux（PySide6/Qt/lib .so）两种布局。

用法: python tools/trim_dist.py [dist目录]
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "PhotoManager")

KEEP_LANG_FRAGMENTS = ("zh_cn", "zh_tw", "en")
DROP_LANG_FRAGMENTS = ("assistant", "designer", "linguist", "qt_help")
DROP_SO_FRAGMENTS = ("webengine", "webchannel", "qt6pdf", "qtquick3d", "qt3d",
                     "qtmultimedia", "qttexttospeech", "qtspatialaudio", "qtpdf")

removed = 0


def rm(path: str) -> None:
    global removed
    if os.path.isdir(path):
        size = sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())
        shutil.rmtree(path, ignore_errors=True)
        removed += size
        print(f"rm dir  {os.path.relpath(path, DIST)} ({size / 1e6:.1f}MB)")
    elif os.path.exists(path):
        removed += os.path.getsize(path)
        os.remove(path)
        print(f"rm file {os.path.relpath(path, DIST)}")


# Qt 资源可位于 PySide6 顶层（Windows）或 PySide6/Qt（Linux）
bases = [os.path.join(DIST, "_internal", "PySide6")]
alt = os.path.join(DIST, "_internal", "PySide6", "Qt")
if os.path.isdir(alt):
    bases.append(alt)

for base in bases:
    for sub in ("resources", "metatypes", "include", "typesystems", "glue",
                "scripts", "support", "doc"):
        rm(os.path.join(base, sub))

    for name in os.listdir(base):
        low = name.lower()
        if ("webengine" in low or "qtwebchannel" in low):
            rm(os.path.join(base, name))

    transl = os.path.join(base, "translations")
    if os.path.isdir(transl):
        for name in os.listdir(transl):
            low = name.lower()
            if not low.endswith(".qm"):
                rm(os.path.join(transl, name))
                continue
            keep = any(k in low for k in KEEP_LANG_FRAGMENTS)
            drop = any(k in low for k in DROP_LANG_FRAGMENTS)
            if not keep or drop:
                rm(os.path.join(transl, name))

libdir = os.path.join(alt, "lib")
if os.path.isdir(libdir):
    for name in os.listdir(libdir):
        low = name.lower()
        if any(k in low for k in DROP_SO_FRAGMENTS):
            rm(os.path.join(libdir, name))

for base, dirs, files in os.walk(DIST):
    if "__pycache__" in base:
        rm(base)

print(f"removed total: {removed / 1e6:.1f}MB")
