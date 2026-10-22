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
"""库完整性校验（#7）：只读比对数据库索引与磁盘实际状态。

红线约束：本模块**只读取**，绝不修改原图、绝不删除任何记录。
它回答一个问题——“库里记的和磁盘上的还一致吗？”，分为四类问题：

  missing      文件已不在磁盘（系统外删除/外接盘未连）——不自动处理，
               由用户去回收站决定（恢复或清除），符合“程序不擅自删除”红线。
  changed      文件在，但大小或修改时间与库不符（被外部工具改动/替换过），
               索引里的 EXIF、缩略图、人脸、OCR 可能已过期 —— 可重新分析修复。
  thumbMissing 原图在，但缩略图文件丢失，网格会显示空白 —— 可重新分析修复。
  error        原图在，但分析阶段失败（status='error'）—— 可重新分析修复。
  decodeError  原图在，但全图数据无法解码（截断/损坏；0.5.64）——不自动处理，
               网格/查看器会显示 ⚠ 标记，预览用相机内嵌图兜底。可经
               deep_decode_check 主动扫描发现（对未验证的非常规格式逐张试解码）。

修复（重跑分析）只重建库内派生数据（缩略图/元数据/向量），不触碰原图。
"""
from __future__ import annotations

import os

# 五类问题的稳定顺序（UI 展示与 repair 均按此）
KINDS = ("missing", "changed", "thumbMissing", "error", "decodeError")

KIND_LABELS = {
    "missing": "文件缺失",
    "changed": "文件被改动",
    "thumbMissing": "缩略图丢失",
    "error": "分析失败",
    "decodeError": "无法解码",
}

# 可修复（重跑分析）的类别；missing 不可自动修复
REPAIRABLE = ("changed", "thumbMissing", "error")

# mtime 比较容差（秒）：不同文件系统/时区写入精度差异，1 秒内视为未变
MTIME_TOLERANCE = 1.0


def _exists(path) -> bool:
    """判断路径存在；兼容库里存的 file:/// URL 形式。"""
    if not path:
        return False
    s = str(path)
    if s.startswith("file:///"):
        s = s[8:]
    elif s.startswith("file://"):
        s = s[7:]
    try:
        return os.path.exists(s)
    except (OSError, ValueError):
        return False


def check_integrity(db, progress_cb=None) -> dict:
    """遍历库中全部照片，比对磁盘状态，返回报告。

    纯读操作，不写库、不碰原图。

    :return: {"total": int, "ok": int,
              "counts": {kind: n, ...},
              "ids": {kind: [id, ...], ...}}
    """
    conn = db.conn
    rows = conn.execute(
        "SELECT id, file_path, file_size, file_mtime, thumbnail_path, status,"
        " decode_error FROM photos"
    ).fetchall()
    total = len(rows)

    ids: dict[str, list] = {k: [] for k in KINDS}
    ok = 0

    for i, (pid, path, size, mtime, thumb, status, decode_error) in enumerate(rows, 1):
        if progress_cb and i % 200 == 0:
            progress_cb(i, total)

        if not _exists(path):
            ids["missing"].append(pid)
            continue

        problem = False
        # 1) 被改动：大小或 mtime 与库不符
        try:
            st = os.stat(str(path))
            if size is not None and int(size) != int(st.st_size):
                ids["changed"].append(pid)
                problem = True
            elif mtime is not None and abs(float(mtime) - st.st_mtime) > MTIME_TOLERANCE:
                ids["changed"].append(pid)
                problem = True
        except OSError:
            # 无法 stat（权限/损坏介质）：当作缺失处理，保守不误判为改动
            ids["missing"].append(pid)
            continue

        # 2) 缩略图丢失（原图在，但缩略图没了）
        if not _exists(thumb):
            ids["thumbMissing"].append(pid)
            problem = True

        # 3) 分析失败
        if status == "error":
            ids["error"].append(pid)
            problem = True

        # 4) 全图数据无法解码（0.5.64：查看时/深度检查发现的损坏标记）
        if decode_error:
            ids["decodeError"].append(pid)
            problem = True

        if not problem:
            ok += 1

    if progress_cb:
        progress_cb(total, total)

    return {
        "total": total,
        "ok": ok,
        "counts": {k: len(ids[k]) for k in KINDS},
        "ids": ids,
    }


def deep_decode_check(conn, progress_cb=None) -> dict:
    """深度解码检查（0.5.64）：对非常规格式逐张试解码，发现损坏文件。

    背景：部分损坏的文件（文件头+内嵌预览完好、全图数据截断/损坏）在
    导入时无法廉价发现——缩略图走内嵌图必成功、元数据正常。只有全图
    解码失败才是确凿证据。本函数对尚未验证的非常规格式照片逐张做
    **最廉价的整图布局校验**（RAW 用 raw_image_visible，不做去马赛克/
    白平衡，比真解码快一个量级；HEIC/AVIF/JXL 等用 Pillow 全量 load）。

    - 只写 photos.decode_error 标记，绝不修改/删除原图（红线）。
    - 已标记(=1)的跳过；Qt 原生格式（jpg/png 等）不在范围——它们损坏时
      通常显示花图而非报错，无法廉价检测，且此类文件导入时缩略图失败
      已走 status='failed' 路径。
    - 实测量级：RAW 200~400ms/张，损坏文件 17ms 即报错。

    :return: {"scanned": n, "damaged": n, "damaged_ids": [...],
              "elapsed": 秒}
    """
    import time as _time

    from photo_manager.core.extractor import QT_NATIVE_EXTS, _RAW_EXTS

    t0 = _time.perf_counter()
    rows = conn.execute(
        "SELECT id, file_path, ext FROM photos"
        " WHERE status != 'missing' AND decode_error = 0"
    ).fetchall()

    damaged: list[int] = []
    scanned = 0
    for i, (pid, path, ext) in enumerate(rows, 1):
        if progress_cb and i % 20 == 0:
            progress_cb(i, len(rows))
        e = (ext or "").lower()
        if not e or e in QT_NATIVE_EXTS:
            continue  # 原生格式不在可检范围
        scanned += 1
        ok = False
        try:
            if e in _RAW_EXTS:
                import rawpy  # noqa: PLC0415

                with rawpy.imread(str(path)) as raw:
                    # 只触达全图数据布局（不解码显示，最小开销验证完整性）
                    arr = raw.raw_image_visible
                    if arr is not None:
                        _ = arr.shape
            else:
                from PIL import Image  # noqa: PLC0415
                from photo_manager.core import extractor as _ex

                with Image.open(str(path)) as im:
                    im.load()  # 全量解码（含 heif/avif opener 注册后的像素读取）
            ok = True
        except Exception:
            ok = False
        if not ok:
            conn.execute(
                "UPDATE photos SET decode_error=1 WHERE id=?", (pid,))
            damaged.append(pid)

    conn.commit()
    elapsed = _time.perf_counter() - t0
    if progress_cb:
        progress_cb(len(rows), len(rows))
    return {
        "scanned": scanned,
        "damaged": len(damaged),
        "damaged_ids": damaged,
        "elapsed": round(elapsed, 1),
    }
