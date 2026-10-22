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
"""真实照片集验收：用 test_data_real（Unsplash 真实照片 + 注入 EXIF）跑完整管线。

验证：入库 / EXIF 完整（相机+时间+GPS）/ 事件聚类 / 人脸检测 / OCR。
用法：python tools/accept_real.py [--src test_data_real] [--limit N]
"""
import argparse
import multiprocessing
import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="test_data_real", help="真实照片根目录")
    ap.add_argument("--limit", type=int, default=0,
                    help="人脸/OCR 最多处理张数（0=全部，qemu 慢环境用）")
    args = ap.parse_args()

    sys.path.insert(0, ROOT)
    os.chdir(ROOT)

    from photo_manager.core.db import Database
    from photo_manager.core.pipeline import IngestPipeline
    from photo_manager.core.events import EventClusterer
    from photo_manager.core.faces import FacePipeline
    from photo_manager.core.facecluster import FaceClusterer
    from photo_manager.core.ocr import OCRPipeline

    FAIL: list = []

    def check(cond, label):
        print(("PASS" if cond else "FAIL"), label)
        if not cond:
            FAIL.append(label)

    src = Path(ROOT) / args.src
    if not src.is_dir():
        print("缺少真实照片目录:", src)
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="accept_real_"))
    db = Database(str(tmp / "real.db")).connect()
    work = tmp / "work"
    work.mkdir(exist_ok=True)

    st = IngestPipeline(db, str(work)).ingest(
        [str(src)], progress_cb=lambda i, t, p: None)
    check(st["indexed"] > 0 and st["failed"] == 0,
          f"入库 indexed={st['indexed']} failed={st['failed']}")

    rows = db.conn.execute(
        "SELECT file_name, camera_make, camera_model, taken_at, gps_lat, gps_lon"
        " FROM photos").fetchall()
    with_exif = [r for r in rows if r[2] and r[3]]
    check(len(with_exif) > 0, f"EXIF 完整（相机+时间） {len(with_exif)}/{len(rows)}")
    has_gps = [r for r in rows if r[4] and r[5]]
    check(len(has_gps) > 0, f"GPS 坐标 {len(has_gps)}")

    ev = EventClusterer(db, gap_hours=4.0).run()
    check(ev["events"] > 0, f"事件聚类 events={ev['events']}")

    limit = args.limit or None
    faces = FacePipeline(db, str(Path(ROOT) / "models")).run(
        limit=limit, workers=1, progress_cb=None)
    check(faces["failed"] == 0, f"人脸扫描 failed={faces['failed']} 检出 {faces['faces']} 张")
    check(faces["faces"] > 0, "人脸有检出（真实人像可识别）")

    # 聚类质量：近重复（同源照片，余弦≈1.0）必须同簇；明显不同人脸（<0.2）不得并簇
    if faces["faces"] > 0:
        cl = FaceClusterer(db, threshold=0.5).run()
        check(cl["persons"] > 0, f"人脸聚类 persons={cl['persons']}（faces={cl['faces']}）")
        import numpy as np

        rows = db.conn.execute(
            "SELECT f.descriptor, f.person_id FROM faces f WHERE f.descriptor IS NOT NULL"
        ).fetchall()
        dim = 128
        if rows:
            raw = b"".join(r[0] for r in rows)
            desc = np.frombuffer(raw, dtype=np.float32).reshape(len(rows), dim)
            norm = desc / np.linalg.norm(desc, axis=1, keepdims=True)
            sim = norm @ norm.T
            np.fill_diagonal(sim, 0.0)
            pids = [r[1] for r in rows]
            # 近重复（同源照片 sim≥0.99）若被分到不同人 = 分裂错误
            near_dup_split = sum(
                1 for i in range(len(rows)) for j in range(i + 1, len(rows))
                if sim[i][j] >= 0.99 and pids[i] != pids[j]
            )
            check(near_dup_split == 0,
                  f"近重复人脸未分裂（sim≥0.99 却不同簇的 {near_dup_split} 对）")
            # 明显不同的人脸（sim≤0.30，远低于阈值 0.5）不得被链式误并进同一人
            far_merge = sum(
                1 for i in range(len(rows)) for j in range(i + 1, len(rows))
                if sim[i][j] <= 0.30 and pids[i] == pids[j]
            )
            check(far_merge == 0,
                  f"明显不同人脸未误并（sim≤0.30 却同簇的 {far_merge} 对）")

    ocr = OCRPipeline(db).run(limit=limit, workers=1, progress_cb=None)
    check(ocr["failed"] == 0, f"OCR 扫描 failed={ocr['failed']} 文本段 {ocr['texts']}")

    db.close()
    print("REAL FAILURES:", FAIL if FAIL else "none")
    return 1 if FAIL else 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
