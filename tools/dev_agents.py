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
"""开发智能体流水线：规划 → 开发 → 测试 → 检查 → 评估。

- 每步结束自动进入下一步；检测到暂停文件 data/.dev_pause 即停止（也支持 Ctrl+C）。
- 规划/开发/评估 为 LLM 智能体，产出与验证放在 docs/agents/ 交接文件；
  测试/检查/评估中的机械校验在此脚本内真实执行。
- 低风险约束：本流水线不做任何删除真实文件 / 外部网络 / 系统配置等高风险操作。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAUSE_FILE = ROOT / "data" / ".dev_pause"
HANDOFF = ROOT / "docs" / "agents"
PY = sys.executable

# 智能体角色定义
AGENTS = {
    "planner": {
        "role": "规划智能体",
        "name": "planner",
        "job": "分析需求与现状，输出可执行的功能清单（优先级/风险/涉及文件/验收标准）",
        "artifacts": ["PLAN.md"],
    },
    "developer": {
        "role": "开发智能体",
        "name": "developer",
        "job": "按计划实现功能，遵守代码风格与既有约定，不做低风险外的操作",
        "artifacts": ["DEV.md"],
    },
    "tester": {
        "role": "测试智能体",
        "name": "tester",
        "job": "编写并运行单元/集成测试，确保新功能有覆盖、旧功能不回归",
        "artifacts": ["TEST.md"],
    },
    "checker": {
        "role": "检查智能体",
        "name": "checker",
        "job": "语法/静态检查 + QML 冒烟 + GUI 交互回归（gui_check），确认无回归",
        "artifacts": ["CHECK.md"],
    },
    "evaluator": {
        "role": "评估智能体",
        "name": "evaluator",
        "job": "按真人使用标准评估（功能完整性/操作方便/视觉/性能/风险），给出满意/继续结论",
        "artifacts": ["EVAL.md"],
    },
}

ORDER = ["planner", "developer", "tester", "checker", "evaluator"]


def pausing() -> bool:
    return PAUSE_FILE.exists()


def log(cycle: str, agent: str, msg: str) -> None:
    HANDOFF.mkdir(parents=True, exist_ok=True)
    with open(HANDOFF / f"run_{cycle}.log", "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {agent}: {msg}\n")
    print(f"[{agent}] {msg}", flush=True)


def _handoff(cycle: str, agent: str) -> Path:
    return HANDOFF / f"{agent}_{cycle}.md"


def has_handoff(cycle: str, agent: str) -> bool:
    p = _handoff(cycle, agent)
    return p.exists() and p.stat().st_size > 0


def run_tester(cycle: str) -> bool:
    log(cycle, "tester", "运行单元/集成测试 …")
    r = subprocess.run([PY, "-m", "unittest", "discover", "-s", "tests"],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    ok = r.returncode == 0
    log(cycle, "tester", f"单测 {'通过' if ok else '失败'}")
    with open(_handoff(cycle, "tester"), "w", encoding="utf-8") as f:
        f.write(f"# 测试报告 {cycle}\n\n```\n{r.stdout[-1200:]}\n{r.stderr[-1200:]}\n```\n")
    return ok


def run_checker(cycle: str) -> bool:
    log(cycle, "checker", "语法编译检查 …")
    r1 = subprocess.run([PY, "-m", "compileall", "-q", "-f",
                         str(ROOT / "photo_manager"), str(ROOT / "tests")],
                        cwd=ROOT, capture_output=True, text=True, timeout=300)
    log(cycle, "checker", f"compileall {'通过' if r1.returncode == 0 else '失败'}")
    log(cycle, "checker", "QML 冒烟 + GUI 回归（gui_check）…")
    r2 = subprocess.run([PY, "-m", "tests.smoke_ui"], cwd=ROOT,
                        capture_output=True, text=True, timeout=300)
    r3 = subprocess.run([PY, str(ROOT / "tools" / "gui_check.py")], cwd=ROOT,
                        capture_output=True, text=True, timeout=900)
    ok = r1.returncode == 0 and r2.returncode == 0 and r3.returncode == 0
    tail3 = (r3.stdout or r3.stderr or "")[-400:]
    log(cycle, "checker", f"smoke={'通过' if r2.returncode == 0 else '失败'} "
                          f"gui_check={'通过' if r3.returncode == 0 else '失败'}")
    with open(_handoff(cycle, "checker"), "w", encoding="utf-8") as f:
        f.write(f"# 检查报告 {cycle}\n\nsmoke:\n```\n{r2.stdout[-500:]}\n```\n"
                f"gui_check:\n```\n{tail3}\n```\n")
    return ok


def run_evaluator(cycle: str) -> bool:
    log(cycle, "evaluator", "真实照片全管线验收（accept_real）…")
    r = subprocess.run([PY, str(ROOT / "tools" / "accept_real.py")], cwd=ROOT,
                       capture_output=True, text=True, timeout=900)
    ok = r.returncode == 0
    tail = (r.stdout or r.stderr or "")[-600:]
    log(cycle, "evaluator", f"accept_real {'全部通过' if ok else '存在失败'}")
    with open(_handoff(cycle, "evaluator"), "w", encoding="utf-8") as f:
        f.write(f"# 评估报告 {cycle}\n\n```\n{tail}\n```\n")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="开发智能体流水线")
    ap.add_argument("--cycle", required=True, help="周期标识，如 C1")
    ap.add_argument("--from", dest="start", default="planner")
    ap.add_argument("--to", default="evaluator")
    args = ap.parse_args()

    print("=" * 64)
    print(f"流水线启动：周期 {args.cycle}  {args.start} → {args.to}")
    print("暂停方式：创建 data/.dev_pause 文件，或 Ctrl+C")
    print("=" * 64)

    idx = ORDER.index(args.start)
    end = ORDER.index(args.to)
    for agent in ORDER[idx:end + 1]:
        meta = AGENTS[agent]
        if pausing():
            log(args.cycle, "pipeline", "检测到暂停文件，流水线停止")
            return 2
        log(args.cycle, agent, f"开始：{meta['job']}")
        if agent == "tester":
            ok = run_tester(args.cycle)
            if not ok:
                log(args.cycle, "pipeline", "测试未通过，暂停流水线等待人工/开发修复")
                return 1
        elif agent == "checker":
            ok = run_checker(args.cycle)
            if not ok:
                log(args.cycle, "pipeline", "检查未通过，暂停流水线")
                return 1
        elif agent == "evaluator":
            run_evaluator(args.cycle)
        else:
            # 规划/开发为 LLM 智能体：等交接文件（PLAN/DEV 由编排者写入）
            log(args.cycle, agent, f"等待交接文件 {_handoff(args.cycle, agent).name}")
            for _ in range(60 * 30):
                if pausing():
                    log(args.cycle, "pipeline", "检测到暂停文件，流水线停止")
                    return 2
                if has_handoff(args.cycle, agent):
                    break
                time.sleep(1)
            if not has_handoff(args.cycle, agent):
                log(args.cycle, "pipeline", f"等待 {agent} 交接文件超时")
                return 1
        log(args.cycle, agent, f"完成：{meta['artifacts']}")

    log(args.cycle, "pipeline", "周期完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())