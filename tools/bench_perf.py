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
"""大库性能基准：搜索/统计/事件聚类/重复哈希/页面查询 耗时。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from photo_manager.core.db import Database
from photo_manager.core.search import PhotoSearch

DB = sys.argv[1] if len(sys.argv) > 1 else "data/perf_test.db"
db = Database(DB).connect()
s = PhotoSearch(db)

def bench(label, fn, repeat=3):
    best = 1e9
    for _ in range(repeat):
        t0 = time.perf_counter()
        n = fn()
        best = min(best, time.perf_counter() - t0)
    print(f"{label:44s} {best*1000:9.1f} ms   ({n} 结果)")
    return best

# 1) FTS 关键词（前缀）
bench("搜索: 公司年会 (FTS 目录)", lambda: len(s.query("公司年会")), 5)
bench("搜索: canon (FTS 相机)", lambda: len(s.query("canon")), 5)
bench("搜索: IMG_000123 (文件名)", lambda: len(s.query("IMG_000123")), 5)

# 2) 高级条件
bench("搜索: tag:xxx (空结果 LIKE)", lambda: len(s.query("tag:不存在标签")), 5)
bench("搜索: camera:sony", lambda: len(s.query("camera:sony")), 5)
bench("搜索: date:2024-03-15", lambda: len(s.query("date:2024-03-15")), 5)
bench("搜索: dates:2024-01-01..2024-06-30", lambda: len(s.query("dates:2024-01-01..2024-06-30")), 5)
bench("搜索: faces:0 (范围扫)", lambda: len(s.query("faces:0")), 5)
bench("搜索: folder:海边 (LIKE 含)", lambda: len(s.query("folder:海边")), 5)

# 3) 页面级查询（GUI 相册首屏）
def page(limit=500):
    rows = db.conn.execute(
        "SELECT id, thumbnail_path, file_name, taken_at, face_count, has_text,"
        " camera_model, file_path, width, height FROM photos"
        " ORDER BY COALESCE(taken_at,'') DESC LIMIT ?", (limit,)
    ).fetchall()
    return len(rows)
bench("相册首屏 500 张 (ORDER BY taken_at)", page, 5)

# 4) 统计
def stats():
    c = db.conn
    n = c.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
    f = c.execute("SELECT COUNT(*) FROM photos WHERE face_count>0").fetchone()[0]
    return n + f
bench("统计 COUNT", stats, 5)

# 5) 事件聚类（全库时间排序 + 分桶）
from photo_manager.core.events import EventClusterer
def ev():
    st = EventClusterer(db, gap_hours=4.0).run()
    return st["events"]
bench("事件聚类 20 万张", ev)

# 6) 人脸聚类（合成 3 万张脸，特征随机——仅测规模）
from photo_manager.core.facecluster import FaceClusterer
c = db.conn
nfaces = c.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
print(f"faces 现有: {nfaces}（如为 0 则注入合成特征）")
if nfaces == 0:
    import random
    import numpy as np
    rnd = random.Random(7)
    ep_rows = c.execute("SELECT photo_id FROM event_photos").fetchall()
    print(f"事件照片池: {len(ep_rows)}")
    rows = []
    for i in range(1, 30001):
        desc = (np.random.default_rng(i).normal(size=128).astype(np.float32)).tobytes()
        pid = ep_rows[rnd.randrange(len(ep_rows))][0]
        rows.append((pid, f"0,0,100,100", desc, 0.9, None))
    t0 = time.perf_counter()
    c.executemany(
        "INSERT INTO faces(photo_id, bbox, descriptor, score, person_id) VALUES (?,?,?,?,?)",
        rows,
    )
    c.commit()
    print(f"注入 30000 合成人脸: {time.perf_counter()-t0:.1f}s")

def fc():
    st = FaceClusterer(db, threshold=0.637).run()
    return st.get("persons", 0)
bench("人脸聚类 3 万张脸", fc)

db.close()
print("DONE")
