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
"""OCR 管线：RapidOCR 文本识别（模型内置，可离线，多进程并行）。"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import Callable

from photo_manager.core.db import Database
from photo_manager.core.system import auto_workers

log = logging.getLogger(__name__)

_worker = None

RAPIDOCR_CONFIG = str(Path(__file__).parent / "rapidocr_config.yaml")


def _init_worker(_=None) -> None:
    global _worker
    from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415

    _worker = RapidOCR(config_path=RAPIDOCR_CONFIG)


def _work(path: str) -> list[dict]:
    result, _ = _worker(path)
    if not result:
        return []
    out = []
    for item in result:
        quad, text, score = item[0], item[1], float(item[2])
        out.append({
            "text": str(text),
            "conf": score,
            "bbox": json.dumps([[float(x), float(y)] for x, y in quad]),
        })
    return out


class OCRPipeline:
    def __init__(self, db: Database):
        self.db = db

    def run(self, limit: int | None = None, workers: int = 0,
            progress_cb: Callable[[int, int, str], None] | None = None,
            cancel: Callable[[], bool] | None = None) -> dict:
        rows = self.db.conn.execute(
            "SELECT id, file_path FROM photos WHERE ocr_done=0 AND status='indexed' AND media_type='photo'"
            " ORDER BY id" + (" LIMIT ?" if limit else ""),
            (limit,) if limit else (),
        ).fetchall()
        total = len(rows)
        stats = {"scanned": 0, "with_text": 0, "texts": 0, "failed": 0}
        t0 = time.perf_counter()
        if not total:
            stats["sec"] = 0.0
            return stats
        # 用独立连接写库：Linux 下 fork 的 worker 会继承并关闭共享连接，导致父连接失效
        import sqlite3

        conn = sqlite3.connect(self.db.path, timeout=10)
        try:
            nproc = workers or auto_workers()
            try:
                self._run_pool(conn, rows, total, stats, nproc, cancel, progress_cb)
            except BrokenProcessPool:
                # 进程池 worker 崩溃（如打包环境 spawn 失败）→ 降级为单进程重跑
                log.warning("OCR 进程池崩溃，降级为单进程重试")
                self._run_pool(conn, rows, total, stats, 1, cancel, progress_cb)
            conn.commit()
        finally:
            conn.close()
        stats["sec"] = round(time.perf_counter() - t0, 2)
        return stats

    def _run_pool(self, conn, rows, total, stats, nproc, cancel, progress_cb):
        batch = max(4, nproc * 2)
        with ProcessPoolExecutor(max_workers=nproc, initializer=_init_worker) as ex:
            done = 0
            for start in range(0, len(rows), batch):
                if cancel and cancel():
                    break
                chunk = rows[start:start + batch]
                futures = {ex.submit(_work, path): (pid, path) for pid, path in chunk}
                for fut in as_completed(futures):
                    pid, path = futures[fut]
                    try:
                        items = fut.result()
                    except BrokenProcessPool:
                        raise  # 进程池整体崩溃 → 上层降级
                    except Exception as e:
                        stats["failed"] += 1
                        # 识别失败不影响照片索引：保留 indexed，仅记录错误并允许重试
                        conn.execute(
                            "UPDATE photos SET error=?, ocr_done=0 WHERE id=?",
                            (f"ocr: {e}", pid),
                        )
                        done += 1
                        continue
                    try:
                        if items:
                            conn.executemany(
                                "INSERT INTO ocr_texts(photo_id, text, conf, bbox) VALUES (?,?,?,?)",
                                [(pid, it["text"], it["conf"], it["bbox"]) for it in items],
                            )
                            agg = " ".join(it["text"] for it in items)
                            conn.execute(
                                "UPDATE photos SET ocr_text=?, has_text=?, error=NULL, ocr_done=1 WHERE id=?",
                                (agg, 1, pid),
                            )
                            conn.execute(
                                "INSERT OR REPLACE INTO ocr_fts(rowid, ocr_text) VALUES (?,?)", (pid, agg)
                            )
                            stats["with_text"] += 1
                            stats["texts"] += len(items)
                        else:
                            conn.execute("UPDATE photos SET ocr_text='', has_text=0, error=NULL, ocr_done=1 WHERE id=?", (pid,))
                            conn.execute("DELETE FROM ocr_fts WHERE rowid=?", (pid,))
                        stats["scanned"] += 1
                    except Exception as e:
                        stats["failed"] += 1
                        conn.execute(
                            "UPDATE photos SET error=?, ocr_done=0 WHERE id=?", (f"ocr: {e}", pid)
                        )
                    done += 1
                    if progress_cb:
                        progress_cb(done, total, path)
                    if done % 20 == 0:
                        conn.commit()
