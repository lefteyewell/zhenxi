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
"""数据库备份与恢复（VACUUM INTO 在线安全复制，无需停机）。"""
from __future__ import annotations

import logging
import shutil
import sqlite3
import time
from pathlib import Path

from photo_manager.core.db import Database

log = logging.getLogger(__name__)


def backup_db(db: Database, out_dir: str | Path | None = None,
              keep: int = 0) -> Path:
    """在线备份当前数据库到 out_dir/backups（默认 <db 同目录>/backups）。

    使用 VACUUM INTO：事务安全、产生紧凑副本；若 DB 尚无任何表则回退为文件复制。
    keep>0 时只保留最近的 keep 份备份（按文件名时间戳排序轮换）。
    """
    src = Path(db.path)
    out_dir = Path(out_dir) if out_dir else src.parent / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = out_dir / f"library_{stamp}.db"
    if target.exists():
        target = out_dir / f"library_{stamp}_{int(time.time() * 1000) % 100000}.db"
    conn = sqlite3.connect(src)
    try:
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        conn.execute("VACUUM INTO ?", (str(target),))
    except sqlite3.Error as e:
        log.warning("VACUUM INTO 失败，回退为文件复制: %s", e)
        shutil.copy2(src, target)
    finally:
        conn.close()
    if keep > 0:
        _rotate(out_dir, keep)
    return target


def _rotate(out_dir: Path, keep: int) -> None:
    """保留最近的 keep 份 library_*.db 备份，删除更旧的。"""
    try:
        files = sorted(
            (p for p in out_dir.glob("library_*.db") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in files[keep:]:
            try:
                old.unlink()
            except OSError:
                log.warning("删除旧备份失败: %s", old)
    except OSError:
        pass


def restore_db(db_path: str | Path, backup_file: str | Path) -> Path:
    """用备份文件恢复数据库（调用方负责：先备份现状、关闭原连接）。"""
    src = Path(backup_file)
    if not src.exists():
        raise FileNotFoundError(f"备份文件不存在: {src}")
    dst = Path(db_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    for sidecar in (Path(f"{dst}-wal"), Path(f"{dst}-shm")):
        if sidecar.exists():
            for _ in range(20):
                try:
                    sidecar.unlink()
                    break
                except OSError:
                    time.sleep(0.05)
    shutil.copy2(src, dst)
    return dst
