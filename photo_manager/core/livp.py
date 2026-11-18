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
"""苹果 .livp（Live Photo 打包）支持：扫描期解包为正常照片 + 视频两条记录。

.livp 本质是 zip 包（通常 IMG_xxxx.HEIC + IMG_xxxx.MOV）。为让全部现有
分析链（人脸 / OCR / 语义 / 感知哈希 / 缩略图 / 播放）零特判地工作，
扫描器遇到 .livp 时把内部成员解到 data/livp/<sha1>/ 下，按**解包产物**
入库两条正常记录；.livp 源文件本身不入 photos 表，其增量状态（mtime/
size）与产物路径的关联由 livp_sources 表追踪：

    livp_sources(livp_path PK, livp_mtime, livp_size, photo_path, video_path)

- 新增 .livp：解包 → 入库两条 pending 记录
- .livp 变更：重新解包覆盖 → 产物 mtime/size 变化 → 记录置回 pending
- .livp 消失：两条记录标 missing（与照片丢失同语义，不清数据）
- 产物丢失但 .livp 还在（程序目录迁移等）：重新解包恢复

成员选择：
- 照片：HEIC/HEIF/JPG/JPEG 成员中最大者；缺照片成员的 .livp 跳过
- 视频：MOV/MP4 成员中最大者；缺视频成员只入照片记录

folder_path 统一取 .livp 所在文件夹（UI 分组 / 搜索口径与原始位置一致）；
file_path 指向解包产物（数据在 data/ 下，程序内无删除原图功能不受影响）。
"""
from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path

PHOTO_MEMBERS = {".heic", ".heif", ".jpg", ".jpeg"}
VIDEO_MEMBERS = {".mov", ".mp4"}
# 库内 photos.file_path 存绝对路径（历史口径），解包产物同样绝对路径
LIVP_DIR_NAME = "livp"


def livp_cache_dir(db_path: str | Path) -> Path:
    """解包产物缓存目录：data/livp/（DB 所在目录即数据目录）。"""
    return Path(db_path).resolve().parent / LIVP_DIR_NAME


def _pick_members(zf: zipfile.ZipFile) -> tuple[str | None, str | None]:
    """从 zip 成员里挑出（照片, 视频）各一个：同类取最大文件。"""
    photos: list[tuple[int, str]] = []
    videos: list[tuple[int, str]] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        ext = os.path.splitext(info.filename)[1].lower()
        if ext in PHOTO_MEMBERS:
            photos.append((info.file_size, info.filename))
        elif ext in VIDEO_MEMBERS:
            videos.append((info.file_size, info.filename))
    photo = max(photos, key=lambda t: t[0])[1] if photos else None
    video = max(videos, key=lambda t: t[0])[1] if videos else None
    return photo, video


def extract_livp(livp_path: str, db_path: str | Path) -> tuple[str, str] | None:
    """解包 .livp 到缓存目录，返回 (photo_path, video_path|None)。

    解包失败（坏 zip / 无照片成员）返回 None。产物目录按 .livp 路径哈希
    唯一化，重解包直接覆盖同名文件。
    """
    h = hashlib.sha1(os.path.abspath(livp_path).replace("\\", "/").encode("utf-8")).hexdigest()
    out_dir = livp_cache_dir(db_path) / h[:16]
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(livp_path) as zf:
            photo_member, video_member = _pick_members(zf)
            if not photo_member:
                return None
            paths: list[str] = []
            for member in (photo_member, video_member):
                if not member:
                    continue
                # 成员名取 basename（苹果打包无目录层级，防御 zip 内路径）
                dest = out_dir / os.path.basename(member)
                with zf.open(member) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                paths.append(str(dest))
            return paths[0], (paths[1] if len(paths) > 1 else None)
    except Exception:
        return None


def sync_livp(info, db) -> int:
    """把一个 .livp（FileInfo）同步进库：解包 + upsert 两条记录。

    返回受影响记录数（0/1/2）。变更与新增都置 pending（由管线的 pending
    恢复路径捡起分析——extract_metadata 按扩展名自动定 photo/video 与
    face_done/ocr_done 置位，全链路零特判）。
    """
    row = db.conn.execute(
        "SELECT livp_mtime, livp_size, photo_path, video_path"
        " FROM livp_sources WHERE livp_path=?",
        (info.file_path,),
    ).fetchone()
    if row and row[0] == info.file_mtime and row[1] == info.file_size:
        # 源未变；但产物可能因程序目录迁移丢失——缺失即重解包
        if not [p for p in row[2:] if p and not os.path.exists(p)]:
            return 0
    extracted = extract_livp(info.file_path, db.path)
    if not extracted:
        return 0
    photo_path, video_path = extracted
    folder = info.folder_path
    n = 0
    for p in (photo_path, video_path):
        if not p:
            continue
        try:
            st = os.stat(p)
            size, mtime = st.st_size, st.st_mtime
        except OSError:
            continue
        ext = os.path.splitext(p)[1].lower()
        existing = db.conn.execute(
            "SELECT id FROM photos WHERE file_path=?", (p,)
        ).fetchone()
        if existing:
            db.conn.execute(
                "UPDATE photos SET file_mtime=?, file_size=?, status='pending',"
                " error=NULL, folder_path=? WHERE id=?",
                (mtime, size, folder, existing[0]),
            )
        else:
            db.conn.execute(
                "INSERT INTO photos (file_path, file_name, folder_path, ext,"
                " file_size, file_mtime, status, media_type)"
                " VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
                (p, os.path.basename(p), folder, ext, size, mtime,
                 "video" if ext in VIDEO_MEMBERS else "photo"),
            )
        n += 1
    db.conn.execute(
        "INSERT OR REPLACE INTO livp_sources"
        " (livp_path, livp_mtime, livp_size, photo_path, video_path)"
        " VALUES (?, ?, ?, ?, ?)",
        (info.file_path, info.file_mtime, info.file_size, photo_path,
         video_path or ""),
    )
    return n


def check_livp_missing(db) -> int:
    """源 .livp 消失 → 对应记录标 missing（恢复逻辑同照片，scan 兜底）。

    返回标记条数。
    """
    n = 0
    for livp_path, photo_path, video_path in db.conn.execute(
        "SELECT livp_path, photo_path, video_path FROM livp_sources"
    ):
        if os.path.exists(livp_path):
            continue
        for p in (photo_path, video_path):
            if not p:
                continue
            db.conn.execute(
                "UPDATE photos SET status='missing' WHERE file_path=?"
                " AND status!='missing'",
                (p,),
            )
            n += 1
    return n
