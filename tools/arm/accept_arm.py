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
"""aarch64 容器内完整链路验收：独立临时库 + 测试照片，跑核心管线并断言。

步骤：ingest(2张测试图) → faces → ocr → hashes → events → cluster → search → dedupe → backup
注意：qemu 模拟下单张 cv2/onnx 推理 ~1-2 分钟，全量 320 张不可行；
     人脸/OCR 用 limit=2 验证链路功能，ingest/哈希/聚类/搜索/备份全量验证。
"""
import os
import shutil
import sys

ROOT = "/app"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from photo_manager.core.db import Database
from photo_manager.core.pipeline import IngestPipeline
from photo_manager.core.faces import FacePipeline
from photo_manager.core.ocr import OCRPipeline
from photo_manager.core.events import EventClusterer
from photo_manager.core.facecluster import FaceClusterer
from photo_manager.core.search import PhotoSearch
from photo_manager.core.duplicates import DuplicateScanner
from photo_manager.core.backup import backup_db

FAIL = []


def check(cond, label):
    print(("PASS" if cond else "FAIL"), label, flush=True)
    if not cond:
        FAIL.append(label)


db_path = "/tmp/arm_accept.db"
for p in (db_path, db_path + "-wal", db_path + "-shm"):
    if os.path.exists(p):
        os.remove(p)
work = "/tmp/arm_work"
if os.path.exists(work):
    shutil.rmtree(work)
os.makedirs(work, exist_ok=True)

db = Database(db_path).connect()
pipe = IngestPipeline(db, work)
st = pipe.ingest(["/app/test_data"], progress_cb=lambda i, t, p: None)
check(st["indexed"] >= 2 and st["failed"] == 0, f"ingest indexed={st['indexed']} failed={st['failed']}")

faces = FacePipeline(db, "/app/models").run(limit=2, workers=1, progress_cb=None)
check(faces["scanned"] == 2 and faces["failed"] == 0, f"faces scanned={faces['scanned']} faces={faces['faces']}")

ocr = OCRPipeline(db).run(limit=2, workers=1, progress_cb=None)
check(ocr["scanned"] == 2 and ocr["failed"] == 0, f"ocr scanned={ocr['scanned']} texts={ocr['texts']}")

dup = DuplicateScanner(db)
h = dup.compute_hashes(workers=1, progress_cb=None)
check(h["ok"] >= 2, f"hashes ok={h['ok']}")
g = dup.find_duplicates(dist=6)
check(len(g) == 0, f"duplicate groups={len(g)}")

ev = EventClusterer(db, gap_hours=4.0).run()
check(ev["events"] >= 1, f"events={ev['events']}")

fc = FaceClusterer(db, threshold=0.637).run()
check(fc["persons"] >= 0, f"cluster ran persons={fc['persons']}")

c = db.conn
ev_photos = c.execute("SELECT photo_id FROM event_photos").fetchall()
for i in range(20):
    import numpy as np
    desc = np.random.default_rng(i).normal(size=128).astype(np.float32).tobytes()
    pid = ev_photos[i % len(ev_photos)][0]
    c.execute(
        "INSERT INTO faces(photo_id, bbox, descriptor, score, person_id) VALUES (?,?,?,?,?)",
        (pid, "0,0,50,50", desc, 0.9, None))
c.commit()
fc2 = FaceClusterer(db, threshold=0.637).run()
check(fc2["persons"] >= 1, f"cluster with injected faces persons={fc2['persons']}")

s = PhotoSearch(db)
n = len(s.query("年会"))
check(n >= 1, f"search hits={n}")

b = backup_db(db)
check(b is not None and os.path.exists(b), f"backup exists={bool(b)}")

db.close()
print("ARM FAILURES:", FAIL if FAIL else "none", flush=True)
sys.exit(1 if FAIL else 0)
