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
"""冒烟测试：无界面启动应用，验证 QML 全部模块可加载、主题可切换。"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Windows 优先项目 venv；其余平台（Linux/macOS 容器等）用当前解释器（0.5.66）
if sys.platform.startswith("win") and os.path.exists(
        os.path.join(ROOT, ".venv", "Scripts", "python.exe")):
    PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
else:
    PY = sys.executable


def main() -> int:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = ROOT
    proc = subprocess.run(
        [PY, "-m", "photo_manager", "--smoke"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        print("smoke: FAILED")
        return 1
    print("smoke: OK - QML 全部页面、LibraryBridge 与主题系统正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
