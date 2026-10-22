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
"""人脸管线：YuNet 检测 + SFace 特征提取（OpenCV Zoo 模型，可离线，多进程并行）。"""
from __future__ import annotations

import json
import logging
import math
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import Callable

import numpy as np

from photo_manager.core.db import Database
from photo_manager.core.system import auto_workers, max_dim

log = logging.getLogger(__name__)

_worker = None


def _exif_orientation(path: str) -> int:
    """读取 EXIF Orientation（0x0112），失败或缺失返回 1。"""
    try:
        from PIL import Image  # noqa: PLC0415

        with Image.open(path) as im:
            return int(im.getexif().get(0x0112, 1))
    except Exception:
        return 1

MAX_DIM = max_dim()  # 人脸检测前图像最长边上限（像素）


def _init_worker(models_dir: str) -> None:
    global _worker
    _worker = FaceService(models_dir)


def _work(path: str) -> list[dict]:
    return _worker.process_image(path)


class FaceService:
    def __init__(self, models_dir: str | Path):
        self.models_dir = Path(models_dir)
        self._detector = None
        self._recognizer = None

    def _load(self):
        if self._detector is None:
            import cv2  # noqa: PLC0415

            self._detector = cv2.FaceDetectorYN_create(
                str(self.models_dir / "face_detection_yunet_2023mar.onnx"),
                "",
                (320, 320), 0.6, 0.3, 5000,
            )
            self._recognizer = cv2.FaceRecognizerSF_create(
                str(self.models_dir / "face_recognition_sface_2021dec.onnx"), ""
            )
        return self._detector, self._recognizer

    def detect(self, img: np.ndarray) -> list[dict]:
        """返回 [{bbox: [x,y,w,h], landmarks: [5点], score, row: 完整15元素}]。"""
        detector, _ = self._load()
        h, w = img.shape[:2]
        detector.setInputSize((w, h))
        _, faces = detector.detect(img)
        if faces is None:
            return []
        out = []
        for f in faces:
            row = np.asarray(f, dtype=np.float32)
            out.append({
                "bbox": [float(v) for v in row[:4]],
                "landmarks": [float(v) for v in row[4:14]],
                "score": float(row[14]),
                "row": row,
            })
        return out

    def feature(self, img: np.ndarray, face: dict) -> np.ndarray:
        _, recognizer = self._load()
        # alignCrop 需要完整 15 元素行（bbox+右眼+左眼+鼻尖+右嘴角+左嘴角），
        # 只用 bbox 会导致裁剪错位、特征提取结果无效。
        aligned = recognizer.alignCrop(img, face["row"])
        return recognizer.feature(aligned).flatten()

    def process_image(self, img_path: str) -> list[dict]:
        """处理单张图，返回 [{bbox, score, descriptor(bytes)}]。
        先按 MAX_DIM 限制最长边（大图检测内存可控，特征由统一缩放保证一致性）。"""
        import cv2  # noqa: PLC0415

        img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"无法读取图片: {img_path}")
        # Windows 上 imdecode 不应用 EXIF 旋转，竖拍照片需手动转正，
        # 否则 bbox 坐标与缩略图（PIL 已 exif_transpose）不对应、特征不准。
        img = self._apply_orientation(img, _exif_orientation(img_path))
        h, w = img.shape[:2]
        scale = min(1.0, MAX_DIM / max(h, w))
        if scale < 1.0:
            img = cv2.resize(img, (int(w * scale), int(h * scale)),
                             interpolation=cv2.INTER_AREA)
        out = []
        for face in self.detect(img):
            feat = self.feature(img, face)
            out.append({
                "bbox": face["bbox"],
                "score": face["score"],
                "descriptor": feat.astype(np.float32).tobytes(),
            })
        return out

    @staticmethod
    def _apply_orientation(img: np.ndarray, orientation: int) -> np.ndarray:
        import cv2  # noqa: PLC0415

        if orientation == 3:
            return cv2.rotate(img, cv2.ROTATE_180)
        if orientation == 6:
            return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        if orientation == 8:
            return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return img


def _read_image(img_path: str) -> np.ndarray:
    """读图（cv2 读不了中文路径，np.fromfile+imdecode），按 MAX_DIM 缩放。"""
    import cv2  # noqa: PLC0415

    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"无法读取图片: {img_path}")
    h, w = img.shape[:2]
    scale = min(1.0, MAX_DIM / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA)
    return img


def search_by_face(db: Database, image_path: str, models_dir: str | Path,
                   min_sim: float = 0.30, top_k: int = 2000) -> list[tuple[int, float]]:
    """上传人脸搜图：检测图中最大人脸 → SFace 特征 → 与库内人脸向量余弦比对。

    纯只读（不写库、不动原图）。同一照片取最高分，返回 [(photo_id, score)]
    按相似度降序；min_sim 过滤噪声（SFace 同人常用阈值 0.363，此处放宽展示）。
    """
    import cv2  # noqa: PLC0415

    svc = FaceService(models_dir)
    img = _read_image(image_path)
    detections = svc.detect(img)
    if not detections:
        raise ValueError("图中未检测到人脸")
    face = max(detections, key=lambda f: f["score"])
    feat = svc.feature(img, face).astype(np.float32)
    fnorm = float(np.linalg.norm(feat)) or 1.0

    best: dict[int, float] = {}
    for pid, desc in db.conn.execute(
        "SELECT photo_id, descriptor FROM faces WHERE hidden=0"
    ):
        if not desc or len(desc) % 4 != 0:
            continue  # 畸形向量（历史残留/中断写入），跳过而非崩溃
        v = np.frombuffer(desc, dtype=np.float32)
        if v.size != feat.size:
            continue  # 维度不符（不同识别模型产物），不可比
        denom = fnorm * (float(np.linalg.norm(v)) or 1.0)
        if denom <= 0:
            continue
        sim = float(np.dot(feat, v) / denom)
        if sim >= min_sim and sim > best.get(pid, -1.0):
            best[pid] = sim
    return sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:top_k]


def _blur_index(img: np.ndarray) -> int:
    """人脸裁剪图 → 模糊指数 0-100（越大越模糊）。

    0.5.42 重做。0.5.40 的「判别比」(原图 Laplacian 方差 ÷ 高斯后方差) 非单调：
    清晰脸被高斯削掉的高频仍占大头 → ratio 偏大（实测清晰脸 idx 19~62 跨度大），
    按阈值清理会把**清晰但纹理丰富的脸**误判为模糊。

    新算法（归一化高频能量比，内容 / 尺寸双重无关）：
    1. 中心 80% 区域（排除 bbox 外扩带进的背景）；
    2. 灰度图做 2D FFT，取幅度谱 P；频率按 Nyquist 归一化；
    3. frac = ΣP(高频带) / ΣP(中高频带)。
       - 分子 = 真正的细节高频能量；分母 = 中高频能量（已剔除 DC 与极低频的
         光照斜坡），分子分母同随人脸内容增减 → 比值只反映「有多少中高频细节
         被保留」，即锐利度；
       - 频率按 Nyquist 归一 → 与裁剪像素数（分辨率）无关；
    4. 模糊 = 低通滤波 → 能量被压向低频，frac 趋小 → 指数趋大；
       纯色/近纯色 frac≈0 → 100（无从辨认，按最糊处理）；
    5. 对数映射（frac 跨数量级）：idx = 100·(ln frac−ln FMAX)/(ln FMIN−ln FMAX)，
       frac≥FMAX→0，frac≤FMIN→100。清晰脸 frac 大 → idx 低；糊脸 frac 极小 → idx 高。
    """
    import cv2  # noqa: PLC0415

    h, w = img.shape[:2]
    y1, y2 = int(h * 0.10), max(int(h * 0.10) + 8, int(h * 0.90))
    x1, x2 = int(w * 0.10), max(int(w * 0.10) + 8, int(w * 0.90))
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return 100
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float64)
    # 仅对超大裁剪降采样（控计算量，INTER_AREA 等比压缩基本保留锐利度）；
    # 不放大——放大只会把小脸人为抹糊，正是 0.5.37/0.5.40 误报的根源。
    m = max(gray.shape[0], gray.shape[1])
    if m > 256:
        s = 256.0 / m
        gray = cv2.resize(gray, None, fx=s, fy=s,
                          interpolation=cv2.INTER_AREA)
    g = gray - gray.mean()
    if not np.any(g):  # 近乎纯色（过曝/黑脸/极端小脸）：无从判别，按最糊处理
        return 100
    F = np.fft.fft2(g)
    P = np.fft.fftshift(np.abs(F) ** 2)
    hh, ww = P.shape
    cy, cx = hh // 2, ww // 2
    Y, X = np.ogrid[:hh, :ww]
    R = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    rmax = float(min(cx, cy)) or 1.0
    rn = R / rmax * 0.5  # 归一化到 Nyquist 的 0.5
    band = rn >= 0.03    # 中高频带（剔除 DC 与极低频光照斜坡）
    hf = rn >= 0.18      # 真正的高频细节
    denom = P[band].sum()
    if denom <= 0:
        return 100
    frac = P[hf & band].sum() / denom
    FMAX, FMIN = 0.30, 0.01
    frac = min(max(frac, FMIN), FMAX)
    idx = 100.0 * (math.log(frac) - math.log(FMAX)) / (math.log(FMIN) - math.log(FMAX))
    return int(round(max(0.0, min(100.0, idx))))


def backfill_face_blur(db: Database, progress_cb=None,
                       cancel: Callable[[], bool] | None = None,
                       force: bool = False) -> dict:
    """为人脸补模糊评分（faces.blur，0-100，越大越模糊）。

    只写 faces.blur，不动任何其他数据。按照片分组解码（一张图多人脸共用解码）；
    文件缺失的脸 blur=-1（界面显示「无法评估」）。返回统计 dict。
    使用独立 sqlite 连接：_spawn 线程与桥接层共享连接并发写会触发
    pysqlite 语句缓存竞态（0.5.x 教训），faces/ocr/hashes 类任务一律独立连接。
    force=True 时重评全部（算法升级后刷新旧分数用），否则只补 blur IS NULL。
    """
    import cv2  # noqa: PLC0415
    import json  # noqa: PLC0415
    import sqlite3  # noqa: PLC0415

    conn = sqlite3.connect(db.path, timeout=10)
    where = "" if force else " WHERE f.blur IS NULL"
    rows = conn.execute(
        "SELECT f.id, f.photo_id, f.bbox FROM faces f" + where +
        " ORDER BY f.photo_id"
    ).fetchall()
    stats = {"total": len(rows), "scored": 0, "missing": 0}
    cache_pid, cache_img = None, None
    t0 = time.perf_counter()
    done = 0
    try:
        for fid, pid, bbox_json in rows:
            if cancel and cancel():
                break
            if pid != cache_pid:
                cache_pid, cache_img = pid, None
                prow = conn.execute(
                    "SELECT file_path FROM photos WHERE id=?", (pid,)
                ).fetchone()
                if prow and Path(prow[0]).exists():
                    try:
                        cache_img = _read_image(prow[0])
                    except Exception:
                        cache_img = None
            idx = -1
            if cache_img is not None:
                try:
                    bx, by, bw, bh = (float(v) for v in json.loads(bbox_json))
                    h, w = cache_img.shape[:2]
                    mx, my = bw * 0.15, bh * 0.15
                    x1, y1 = max(0, int(bx - mx)), max(0, int(by - my))
                    x2, y2 = min(w, int(bx + bw + mx)), min(h, int(by + bh + my))
                    if x2 - x1 > 4 and y2 - y1 > 4:
                        idx = _blur_index(cache_img[y1:y2, x1:x2])
                        stats["scored"] += 1
                    else:
                        stats["missing"] += 1
                except Exception:
                    stats["missing"] += 1
            else:
                stats["missing"] += 1
            conn.execute("UPDATE faces SET blur=? WHERE id=?", (idx, fid))
            done += 1
            if progress_cb and done % 20 == 0:
                progress_cb(done, stats["total"], "")
            if done % 200 == 0:
                conn.commit()
        conn.commit()
    finally:
        conn.close()
    stats["sec"] = round(time.perf_counter() - t0, 2)
    return stats


class FacePipeline:
    def __init__(self, db: Database, models_dir: str | Path):
        self.db = db
        self.models_dir = str(models_dir)

    def run(self, limit: int | None = None, workers: int = 0,
            progress_cb: Callable[[int, int, str], None] | None = None,
            cancel: Callable[[], bool] | None = None) -> dict:
        rows = self.db.conn.execute(
            "SELECT id, file_path FROM photos WHERE face_done=0 AND status='indexed' AND media_type='photo'"
            " ORDER BY id" + (" LIMIT ?" if limit else ""),
            (limit,) if limit else (),
        ).fetchall()
        total = len(rows)
        stats = {"scanned": 0, "with_faces": 0, "faces": 0, "failed": 0}
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
                log.warning("人脸 进程池崩溃，降级为单进程重试")
                self._run_pool(conn, rows, total, stats, 1, cancel, progress_cb)
            conn.commit()
        finally:
            conn.close()
        stats["sec"] = round(time.perf_counter() - t0, 2)
        return stats

    def _run_pool(self, conn, rows, total, stats, nproc, cancel, progress_cb):
        batch = max(4, nproc * 2)
        with ProcessPoolExecutor(
            max_workers=nproc, initializer=_init_worker, initargs=(self.models_dir,)
        ) as ex:
            done = 0
            for start in range(0, len(rows), batch):
                if cancel and cancel():
                    break
                chunk = rows[start:start + batch]
                futures = {ex.submit(_work, path): (pid, path) for pid, path in chunk}
                for fut in as_completed(futures):
                    pid, path = futures[fut]
                    try:
                        detections = fut.result()
                    except BrokenProcessPool:
                        raise  # 进程池整体崩溃 → 上层降级
                    except Exception as e:
                        stats["failed"] += 1
                        # 识别失败不影响照片索引：保留 indexed，仅记录错误并允许重试
                        conn.execute(
                            "UPDATE photos SET error=?, face_done=0 WHERE id=?",
                            (f"face: {e}", pid),
                        )
                        stats["scanned"] += 1
                        done += 1
                        continue
                    try:
                        if detections:
                            conn.executemany(
                                "INSERT INTO faces(photo_id, bbox, score, descriptor)"
                                " VALUES (?,?,?,?)",
                                [(pid, json.dumps(d["bbox"]), d["score"], d["descriptor"]) for d in detections],
                            )
                            conn.execute("UPDATE photos SET face_count=? WHERE id=?", (len(detections), pid))
                            stats["with_faces"] += 1
                            stats["faces"] += len(detections)
                        conn.execute("UPDATE photos SET face_done=1 WHERE id=?", (pid,))
                    except Exception as e:
                        stats["failed"] += 1
                        conn.execute(
                            "UPDATE photos SET error=?, face_done=0 WHERE id=?",
                            (f"face: {e}", pid),
                        )
                    stats["scanned"] += 1
                    done += 1
                    if progress_cb:
                        progress_cb(done, total, path)
                    if done % 50 == 0:
                        conn.commit()
