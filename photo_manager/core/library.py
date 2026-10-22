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
"""照片库根目录：导入时自动把库外照片复制入库（保持相对结构，只复制照片文件）。

设计要点（与红线一致）：
- 只**新增**文件（shutil.copy2），绝不删除、绝不改动任何源文件；
- 源照片已在任一照片库根目录下 → 就地登记，不复制；
- 复制时保持「源文件夹名/子路径」的相对结构：导入 D:/Photos/2025旅行 中的
  海边/a.jpg → <库根>/2025旅行/海边/a.jpg，同一子文件夹的照片整体归位；
- 非照片文件由扫描器白名单天然过滤，不会进入本模块，更不会被复制；
- 目标重名：同大小视为已复制（幂等），不同则加 _1/_2 后缀；
- 复制失败（磁盘满/权限）：回退为就地登记源文件，不让整次导入失败。

另含定时任务的到期判定（纯函数，便于测试）。
"""
from __future__ import annotations

import datetime
import os
import shutil
from pathlib import Path


def _norm(p: str | Path) -> str:
    """绝对路径 + 正斜杠 + 小写（Windows 不区分大小写）。"""
    return os.path.abspath(str(p)).replace("\\", "/").lower().rstrip("/")


def pick_copy_root(src_size: int, roots, margin_mb: int = 256) -> str | None:
    """从多个照片库根目录中挑选写入目标（0.5.49：空间不足自动换根）。

    策略：
    - 依次探测各根剩余空间，选第一个 ≥ src_size + margin_mb 的根；
    - 都不满足 → 选剩余空间最大的根（尽力而为；复制失败会由
      relocate_file 回退为就地登记，不让整次导入失败）；
    - roots 为空 / 全部不可探测 → None（调用方回退就地登记）。
    """
    roots = [str(r) for r in (roots or []) if r]
    if not roots:
        return None
    need = int(src_size) + margin_mb * 1024 * 1024
    best, best_free = None, -1
    for r in roots:
        try:
            free = shutil.disk_usage(r).free
        except OSError:
            continue  # 根不存在/不可访问：跳过
        if free >= need:
            return r
        if free > best_free:
            best, best_free = r, free
    return best if best is not None else roots[0]


def under_any(path: str | Path, roots) -> bool:
    """path 是否位于 roots 中任一根目录之内（含等于根自身）。"""
    np = _norm(path)
    for r in roots or ():
        nr = _norm(r)
        if np == nr or np.startswith(nr + "/"):
            return True
    return False


def relocate_file(src: str, anchor: str, dest_root) -> str:
    """把库外照片 src 复制到照片库，返回登记用路径。

    - dest_root 可为单个路径或路径列表（0.5.49：多根目录 + 空间不足自动换根，
      由 pick_copy_root 逐张挑选剩余空间足够的根）；
    - src 已在任一 dest_root 下 → 原样返回；
    - 目标结构：<dest_root>/<anchor 目录名>/<src 相对 anchor 的路径>；
    - 目标重名且同大小 → 幂等返回既有文件；不同 → 追加 _N 后缀；
    - 任何复制失败 → 返回 src（就地登记，不中断导入）。
    """
    try:
        src_p = Path(os.path.abspath(src))
        if not src_p.is_file():
            return src
        roots = ([str(dest_root)] if isinstance(dest_root, (str, os.PathLike))
                 else [str(r) for r in (dest_root or []) if r])
        if not roots:
            return src
        if under_any(src_p, roots):
            return str(src_p)
        root = pick_copy_root(src_p.stat().st_size, roots)
        if root is None:
            return src
        anchor_p = Path(os.path.abspath(anchor))
        rel = src_p.relative_to(anchor_p)
        dest_dir = Path(root) / anchor_p.name / rel.parent
        dest = dest_dir / src_p.name
        if dest.exists():
            try:
                if dest.stat().st_size == src_p.stat().st_size:
                    return str(dest)
            except OSError:
                pass
            stem, suffix = src_p.stem, src_p.suffix
            for i in range(1, 1000):
                cand = dest_dir / f"{stem}_{i}{suffix}"
                if not cand.exists():
                    dest = cand
                    break
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_p, dest)
        return str(dest)
    except (OSError, ValueError):
        # ValueError：anchor 与 src 不在同一路径树下时 relative_to 抛出
        # （多扫描根 + 复制入库时锚点回退可能选错根），回退就地登记，不让导入崩溃
        return src


def parse_hhmm(text: str) -> tuple[int, int] | None:
    """"HH:MM" → (h, m)；非法返回 None。"""
    try:
        parts = str(text).strip().split(":")
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except (ValueError, IndexError, AttributeError):
        pass
    return None


def schedule_due(mode: str, time_str: str, last_date: str, once_at: str,
                 now: datetime.datetime) -> bool:
    """定时任务到期判定（纯函数）。

    - mode="daily"：今天尚未运行且当前时间 ≥ 每日设定时间（启动补跑一次）；
    - mode="once"：once_at（"YYYY-MM-DD HH:MM"）合法且 now ≥ once_at；
    - 其他 mode → False。
    """
    mode = (mode or "").strip().lower()
    if mode == "daily":
        hm = parse_hhmm(time_str)
        if hm is None:
            return False
        today = now.strftime("%Y-%m-%d")
        if last_date == today:
            return False
        return (now.hour, now.minute) >= hm
    if mode == "once":
        try:
            at = datetime.datetime.strptime(str(once_at).strip(),
                                            "%Y-%m-%d %H:%M")
        except ValueError:
            return False
        return now >= at
    return False
