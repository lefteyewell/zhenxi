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
"""元数据 CSV 导出：照片清单 + EXIF + 标签 + 评级/旗标（便于外部归档/上报）。"""
from __future__ import annotations

import csv
from pathlib import Path

from photo_manager.core.db import Database

CSV_COLS = [
    "id", "file_path", "file_name", "folder_path", "taken_at",
    "camera_make", "camera_model", "lens_model", "exposure", "f_number",
    "iso", "focal_length", "gps_lat", "gps_lon", "gps_alt",
    "width", "height", "file_size", "face_count", "has_text",
    "rating", "flag", "tags",
]


def export_metadata_csv(db: Database, out_path: str | Path) -> Path:
    """导出全部非 missing 照片的元数据 CSV（UTF-8 BOM，Excel 友好）。"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = db.conn
    rows = c.execute(
        "SELECT id, file_path, file_name, folder_path, COALESCE(taken_at,''),"
        " COALESCE(camera_make,''), COALESCE(camera_model,''), COALESCE(lens_model,''),"
        " COALESCE(exposure,''), f_number, iso, focal_length, gps_lat, gps_lon, gps_alt,"
        " width, height, file_size, face_count, has_text, rating, flag"
        " FROM photos WHERE status != 'missing'"
        " ORDER BY sort_key DESC, id DESC"
    ).fetchall()
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLS)
        for r in rows:
            tags = [t[0] for t in c.execute(
                "SELECT tag FROM photo_tags WHERE photo_id=? ORDER BY tag", (r[0],)
            ).fetchall()]
            w.writerow([*r, ";".join(tags)])
    return out