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
"""虚拟相册：用户自建分组，只存 photos 表引用（album_photos 关联），不移动/复制文件。

与"程序内不删除"红线一致：删除相册只删分组与关联记录，**绝不动任何照片文件**；
照片本身也不受影响（photos 行保留，仍可在其他视图/相册中出现）。

浏览口径：相册视图默认排除 missing 与已归档照片，与主时间轴一致。
"""
from __future__ import annotations

from photo_manager.core.db import Database

ALBUM_ROW_COLS = (
    "SELECT p.id, p.thumbnail_path, p.file_name, p.taken_at, p.face_count,"
    " p.has_text, p.camera_model, p.file_path, p.width, p.height,"
    " p.rating, p.flag, p.color_label"
)


def create_album(db: Database, name: str) -> int:
    """新建相册，返回 id；重名返回 0（UI 提示）。"""
    name = (name or "").strip()
    if not name:
        return 0
    try:
        cur = db.conn.execute("INSERT INTO albums(name) VALUES (?)", (name,))
        db.conn.commit()
        return cur.lastrowid
    except Exception:
        db.conn.rollback()
        return 0


def rename_album(db: Database, album_id: int, name: str) -> bool:
    name = (name or "").strip()
    if album_id <= 0 or not name:
        return False
    try:
        db.conn.execute("UPDATE albums SET name=? WHERE id=?", (name, album_id))
        db.conn.commit()
        return True
    except Exception:
        db.conn.rollback()
        return False


def delete_album(db: Database, album_id: int) -> bool:
    """删除相册（含关联记录）。只删分组，不动照片文件与 photos 行。"""
    if album_id <= 0:
        return False
    try:
        db.conn.execute("DELETE FROM album_photos WHERE album_id=?", (album_id,))
        db.conn.execute("DELETE FROM albums WHERE id=?", (album_id,))
        db.conn.commit()
        return True
    except Exception:
        db.conn.rollback()
        return False


def list_albums(db: Database) -> list[dict]:
    """相册列表：id/name/photoCount/cover（最新一张的缩略图路径，可无）。"""
    conn = db.conn
    rows = conn.execute(
        "SELECT a.id, a.name,"
        " (SELECT COUNT(*) FROM album_photos ap JOIN photos p ON p.id = ap.photo_id"
        "  WHERE ap.album_id = a.id AND p.status != 'missing' AND p.archived = 0)"
        " FROM albums a ORDER BY a.created_at DESC, a.id DESC"
    ).fetchall()
    out = []
    for aid, name, cnt in rows:
        cover = conn.execute(
            "SELECT p.thumbnail_path FROM album_photos ap JOIN photos p ON p.id = ap.photo_id"
            " WHERE ap.album_id = ? AND p.status != 'missing' AND p.archived = 0"
            " ORDER BY p.sort_key DESC, p.id DESC LIMIT 1",
            (aid,),
        ).fetchone()
        out.append({"id": aid, "name": name, "photoCount": cnt,
                    "cover": cover[0] if cover else ""})
    return out


def add_photos(db: Database, album_id: int, photo_ids) -> int:
    """把照片加入相册（已在内自动跳过）。返回实际新增数。"""
    if album_id <= 0:
        return 0
    ids = [int(i) for i in (photo_ids or []) if i is not None]
    if not ids:
        return 0
    n = 0
    try:
        for pid in ids:
            cur = db.conn.execute(
                "INSERT OR IGNORE INTO album_photos(album_id, photo_id) VALUES (?,?)",
                (album_id, pid))
            n += cur.rowcount
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        return 0
    return n


def remove_photos(db: Database, album_id: int, photo_ids) -> int:
    """把照片移出相册（仅移除关联，照片本身不受任何影响）。"""
    if album_id <= 0:
        return 0
    ids = [int(i) for i in (photo_ids or []) if i is not None]
    if not ids:
        return 0
    q = ",".join("?" for _ in ids)
    cur = db.conn.execute(
        f"DELETE FROM album_photos WHERE album_id=? AND photo_id IN ({q})",
        (album_id, *ids))
    db.conn.commit()
    return cur.rowcount


def album_photos(db: Database, album_id: int, limit: int = 500,
                 offset: int = 0) -> list[tuple]:
    """相册内照片行（排除 missing/已归档，按加入时间倒序），供 bridge _pack 使用。"""
    if album_id <= 0:
        return []
    return db.conn.execute(
        f"{ALBUM_ROW_COLS}"
        " FROM album_photos ap JOIN photos p ON p.id = ap.photo_id"
        " WHERE ap.album_id=? AND p.status != 'missing' AND p.archived = 0"
        " ORDER BY ap.added_at DESC, p.id DESC LIMIT ? OFFSET ?",
        (album_id, limit, offset),
    ).fetchall()


def album_count(db: Database, album_id: int) -> int:
    if album_id <= 0:
        return 0
    return db.conn.execute(
        "SELECT COUNT(*) FROM album_photos ap JOIN photos p ON p.id = ap.photo_id"
        " WHERE ap.album_id=? AND p.status != 'missing' AND p.archived = 0",
        (album_id,),
    ).fetchone()[0]
