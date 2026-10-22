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
"""阶段 4 一键验收：单测全量 + CLI 关键链路 + GUI 冒烟 + 打包冒烟。"""
import subprocess
import sys
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")


def run(args, timeout=900, env_extra=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = ROOT
    if env_extra:
        env.update(env_extra)
    t0 = time.perf_counter()
    proc = subprocess.run([PY, *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)
    dt = time.perf_counter() - t0
    return proc, dt


def main() -> int:
    steps = [
        ("单测 pipeline", ["tests/test_pipeline.py"], 600),
        ("单测 cluster", ["tests/test_cluster.py"], 600),
        ("单测 stage3(同步/重复/搜索/备份)", ["tests/test_stage3.py"], 600),
        ("GUI 冒烟", ["tests/smoke_ui.py"], 300),
        ("真实照片验收(EXIF/事件/人脸/OCR)", ["tools/accept_real.py"], 1800),
        ("CLI 统计", ["-m", "photo_manager.cli", "stats"], 120),
        ("CLI 高级搜索", ["-m", "photo_manager.cli", "search", "tag:客户张总", "--limit", "5"], 120),
        ("CLI 重复检测", ["-m", "photo_manager.cli", "dedupe"], 600),
    ]
    failed = []
    for name, args, to in steps:
        try:
            proc, dt = run(args, timeout=to)
            ok = proc.returncode == 0
            print(f"[{'OK ' if ok else 'FAIL'}] {name} ({dt:.1f}s)")
            if not ok:
                print(proc.stdout[-2000:])
                print(proc.stderr[-2000:])
                failed.append(name)
        except subprocess.TimeoutExpired:
            print(f"[FAIL] {name} (超时 {to}s)")
            failed.append(name)
    print("=" * 40)
    print(f"验收结果: {len(steps) - len(failed)}/{len(steps)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
