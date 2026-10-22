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
"""合成大库性能基准：生成 N 行照片 + FTS 同步，测关键操作耗时。

用法: python tools/gen_perf_db.py [行数] [db路径]
"""
import os
import random
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from photo_manager.core.db import Database

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
DB = sys.argv[2] if len(sys.argv) > 2 else "data/perf_test.db"

if os.path.exists(DB):
    os.remove(DB)
for side in (DB + "-wal", DB + "-shm"):
    if os.path.exists(side):
        os.remove(side)

db = Database(DB).connect()
c = db.conn
c.execute("PRAGMA synchronous=OFF")
c.execute("PRAGMA cache_size=-131072")  # 128MB

makes = ["Canon", "Sony", "Nikon", "Fujifilm", "Panasonic"]
models = {
    "Canon": ["EOS R5", "EOS R6 Mark II", "EOS 5D Mark IV"],
    "Sony": ["A7RM5", "A7C II", "A6700"],
    "Nikon": ["Z9", "Z8", "D850"],
    "Fujifilm": ["X-T5", "X100VI"],
    "Panasonic": ["S5II", "G9II"],
}
folders = [
    "D:/photos/2024-01_公司年会", "D:/photos/2024-03_产品发布会",
    "D:/photos/2024-06_海边度假", "D:/photos/2024-09_人物写真",
    "D:/photos/2025-02_雪山徒步", "D:/photos/2025-05_城市夜景",
    "D:/photos/2025-07_婚礼跟拍", "D:/photos/2025-10_展会现场",
]
rnd = random.Random(42)

rows = []
for i in range(1, N + 1):
    make = rnd.choice(makes)
    folder = rnd.choice(folders)
    year = rnd.randint(2020, 2025)
    month = rnd.randint(1, 12)
    day = rnd.randint(1, 28)
    taken = f"{year}-{month:02d}-{day:02d}T{rnd.randint(0,23):02d}:{rnd.randint(0,59):02d}:00"
    name = f"IMG_{rnd.randint(1000, 9999)}.JPG"
    rows.append((
        f"{folder}/IMG_{i:06d}.JPG", name, folder, ".JPG",
        rnd.randint(100_000, 2_000_000), rnd.random() * 2e9, taken,
        make, rnd.choice(models[make]), rnd.choice(["RF50mm F1.2", "24-70mm F2.8", "70-200mm F2.8"]),
        4000, 3000, i % 7 == 0, i % 13 == 0,
        f"D:/thumbs/{i:06d}.jpg",
    ))

t0 = time.perf_counter()
c.executemany(
    "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
    " file_mtime, taken_at, camera_make, camera_model, lens_model,"
    " width, height, face_count, has_text, thumbnail_path)"
    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    rows,
)
c.commit()
ins = time.perf_counter() - t0

db.close()
print(f"rows={N} insert_sec={ins:.1f}")
print(f"size_mb={os.path.getsize(DB) / 1e6:.1f}")
