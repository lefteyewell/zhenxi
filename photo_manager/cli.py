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
"""命令行工具：入库、人脸、OCR、搜索（调试/批处理用）。"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from photo_manager.core.db import Database
from photo_manager.core.faces import FacePipeline
from photo_manager.core.ocr import OCRPipeline
from photo_manager.core.pipeline import IngestPipeline
from photo_manager.core.search import PhotoSearch

DEFAULT_DB = str(Path(__file__).resolve().parent.parent / "data" / "library.db")


def _db(args) -> Database:
    db = Database(args.db).connect()
    return db


def cmd_ingest(args) -> int:
    db = _db(args)
    pipe = IngestPipeline(db, Path(args.db).parent)
    stats = pipe.ingest(
        args.root,
        progress_cb=lambda done, total, path: print(
            f"\r[{done}/{total}] {path[:80]}", end="", flush=True
        ),
    )
    print("\n" + json.dumps(stats, ensure_ascii=False, indent=2))
    db.close()
    return 0


def cmd_faces(args) -> int:
    db = _db(args)
    pipe = FacePipeline(db, args.models)
    stats = pipe.run(
        limit=args.limit, workers=args.workers,
        progress_cb=lambda done, total, path: print(
            f"\r[{done}/{total}] {path[:80]}", end="", flush=True
        ),
    )
    print("\n" + json.dumps(stats, ensure_ascii=False, indent=2))
    db.close()
    return 0


def cmd_ocr(args) -> int:
    db = _db(args)
    pipe = OCRPipeline(db)
    stats = pipe.run(
        limit=args.limit, workers=args.workers,
        progress_cb=lambda done, total, path: print(
            f"\r[{done}/{total}] {path[:80]}", end="", flush=True
        ),
    )
    print("\n" + json.dumps(stats, ensure_ascii=False, indent=2))
    db.close()
    return 0


def cmd_search(args) -> int:
    db = _db(args)
    s = PhotoSearch(db)
    hits = s.query(args.query, limit=args.limit)
    print(f"命中 {len(hits)} 条:")
    for h in hits:
        print(f"  {h['file_path']}  {h['taken_at'] or ''}  脸:{h['face_count']} OCR:{h['has_text']}")
    if args.suggest:
        print("联想:", s.suggest(args.query))
    db.close()
    return 0


def cmd_events(args) -> int:
    db = _db(args)
    from photo_manager.core.events import EventClusterer

    stats = EventClusterer(db, gap_hours=args.gap).run()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    db.close()
    return 0


def cmd_facecluster(args) -> int:
    db = _db(args)
    from photo_manager.core.facecluster import FaceClusterer

    stats = FaceClusterer(db, threshold=args.threshold).run(
        progress_cb=lambda done, total: print(
            f"\r聚类进度 [{done}/{total}]", end="", flush=True
        )
    )
    print("\n" + json.dumps(stats, ensure_ascii=False, indent=2))
    db.close()
    return 0


def cmd_stats(args) -> int:
    db = _db(args)
    for row in db.conn.execute(
        "SELECT status, COUNT(*) FROM photos GROUP BY status ORDER BY status"
    ):
        print(f"{row[0]:10s} {row[1]}")
    for row in db.conn.execute("SELECT path, last_scan_at FROM scan_roots"):
        print(f"root: {row[0]}  (last scan {row[1]})")
    db.close()
    return 0


def cmd_syncexport(args) -> int:
    db = _db(args)
    from photo_manager.core.sync import MetadataSync

    stats = MetadataSync(db).export(args.out)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    db.close()
    return 0


def cmd_syncimport(args) -> int:
    db = _db(args)
    from photo_manager.core.sync import MetadataSync

    stats = MetadataSync(db).import_from(args.file)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    db.close()
    return 0


def cmd_hashes(args) -> int:
    db = _db(args)
    from photo_manager.core.duplicates import DuplicateScanner

    stats = DuplicateScanner(db).compute_hashes(
        limit=args.limit, workers=args.workers,
        progress_cb=lambda done, total: print(
            f"\r哈希进度 [{done}/{total}]", end="", flush=True
        ),
    )
    print("\n" + json.dumps(stats, ensure_ascii=False, indent=2))
    db.close()
    return 0


def cmd_rethumb(args) -> int:
    """重建缩略图（0.5.64）：修复旧版生成的错误方向 RAW 竖版缩略图等。

    默认只处理相机 RAW（非 RAW 的 exif_transpose 自首个版本即在位，
    旧缩略图无方向问题）；--all 全部重建。只动 thumbs 缓存与
    thumb_width/thumb_height 字段，不碰原图。缩略图命名与 pipeline
    _thumb_path 完全一致（sha1(file_path)），重建即原位覆盖。
    """
    import hashlib as _hashlib

    from photo_manager.core.extractor import make_thumbnail
    from photo_manager.core.scanner import RAW_EXTS

    db = _db(args)
    data_dir = Path(args.db).parent
    if args.all:
        rows = db.conn.execute(
            "SELECT id, file_path FROM photos WHERE status != 'missing'"
        ).fetchall()
    else:
        exts = tuple(RAW_EXTS)
        rows = db.conn.execute(
            "SELECT id, file_path FROM photos WHERE status != 'missing' AND"
            " lower(ext) IN (%s)" % ",".join("?" * len(exts)), exts
        ).fetchall()
    thumbs_dir = (data_dir / "thumbs").resolve()
    ok = fail = 0
    for i, (pid, fpath) in enumerate(rows, 1):
        h = _hashlib.sha1(str(fpath).encode("utf-8")).hexdigest()
        thumb = thumbs_dir / h[:2] / (h[2:16] + ".jpg")
        try:
            thumb.parent.mkdir(parents=True, exist_ok=True)
            size = make_thumbnail(str(fpath), thumb)
        except Exception:
            size = None
        if size:
            db.conn.execute(
                "UPDATE photos SET thumb_width=?, thumb_height=? WHERE id=?",
                (size[0], size[1], pid))
            ok += 1
        else:
            fail += 1
        if i % 20 == 0 or i == len(rows):
            print(f"\r缩略图重建 [{i}/{len(rows)}]", end="", flush=True)
    db.conn.commit()
    print(f"\n完成：成功 {ok}，失败/跳过 {fail}（失败多为源文件缺失/损坏）")
    db.close()
    return 0


def cmd_dedupe(args) -> int:
    db = _db(args)
    from photo_manager.core.duplicates import DuplicateScanner

    groups = DuplicateScanner(db).find_duplicates(dist=args.dist)
    total = sum(g["duplicates"] for g in groups)
    print(f"发现 {len(groups)} 组重复，涉及 {total} 张冗余照片（仅报告，不删除）")
    for g in groups[: args.show]:
        print(f"\n重复组（{g['duplicates']} 张冗余）:")
        for m in g["members"]:
            tag = "主" if m["primary"] else "复"
            print(f"  [{tag}] {m['path']}  {m['takenAt']}  {m['width']}x{m['height']}")
    db.close()
    return 0


def cmd_backup(args) -> int:
    db = _db(args)
    from photo_manager.core.backup import backup_db

    target = backup_db(db, args.out)
    print(f"备份完成: {target} ({target.stat().st_size // 1024} KB)")
    db.close()
    return 0


def cmd_tag(args) -> int:
    db = _db(args)
    from photo_manager.core.search import _like_escape

    rows = db.conn.execute(
        "SELECT id FROM photos WHERE file_path LIKE ? ESCAPE '\\'",
        (f"%{_like_escape(args.match)}%",),
    ).fetchall()
    if not rows:
        print(f"未找到匹配照片: {args.match}")
        db.close()
        return 1
    n = 0
    for (pid,) in rows:
        db.conn.execute(
            "INSERT INTO photo_tags(photo_id, tag) VALUES (?,?) "
            "ON CONFLICT(photo_id, tag) DO NOTHING",
            (pid, args.tag),
        )
        n += 1
    db.conn.commit()
    print(f"已为 {n} 张照片打标签 '{args.tag}'")
    db.close()
    return 0


def cmd_restore(args) -> int:
    from photo_manager.core.backup import restore_db

    target = restore_db(args.db, args.file)
    print(f"恢复完成: {target}")
    return 0


_MIN_THUMB_EDGE = 256


def _pick_source(file_path, thumb_path, tw, th, db_path: str = "") -> str:
    """优先用缩略图（解码快）；尺寸过小会失真，退回原图以保证精度。

    0.5.51：thumbnail_path 可能是相对路径（thumbs/…），按 db_path 解析。
    """
    if thumb_path:
        try:
            from photo_manager.core.paths import resolve_data_path

            abs_thumb = resolve_data_path(db_path, thumb_path) if db_path \
                else str(thumb_path)
            if max(tw or 0, th or 0) >= _MIN_THUMB_EDGE and Path(abs_thumb).exists():
                return abs_thumb
        except Exception:
            pass
    return file_path


def cmd_clip_index(args) -> int:
    """为照片/视频生成 Chinese-CLIP 语义向量（增量：只处理尚未生成的）。

    0.5.51：视频按关键帧平均编码（video_frames 表），一并进入语义检索。
    """
    import time

    import numpy as np
    from photo_manager.core.clip import MODEL_ID, encode_indexable, get_service
    from photo_manager.core.db import Database

    svc = get_service(args.models)
    if not svc.available:
        print("未检测到 Chinese-CLIP 模型组件，缺少：" + "、".join(svc.missing_files()))
        print(f"请将模型文件放置于: {svc.dir}")
        return 1

    db = Database(args.db).connect()
    sql = (
        "SELECT p.id, p.file_path, p.thumbnail_path, p.thumb_width, p.thumb_height,"
        " p.media_type "
        "FROM photos p "
        "LEFT JOIN photo_embeddings e ON e.photo_id = p.id AND e.model = ? "
        "WHERE e.photo_id IS NULL AND (p.media_type='photo' OR p.media_type='video')"
    )
    params: list = [MODEL_ID]
    if args.folder:
        sql += " AND p.folder_path LIKE ?"
        params.append(f"%{args.folder}%")
    sql += " ORDER BY p.id"
    if args.limit:
        sql += " LIMIT ?"
        params.append(args.limit)
    rows = db.conn.execute(sql, params).fetchall()
    vframes: dict[int, list[str]] = {}
    for pid_, fp_ in db.conn.execute(
            "SELECT photo_id, path FROM video_frames ORDER BY photo_id, idx"):
        vframes.setdefault(pid_, []).append(fp_)
    if not rows:
        print("所有照片/视频均已生成语义向量，无需处理")
        db.close()
        return 0

    print(f"待生成向量 {len(rows)} 项（首次加载模型约需 10~20 秒）")
    ok = fail = 0
    t0 = time.perf_counter()
    for i, row in enumerate(rows, 1):
        pid = row[0]
        mt = row[5] or "photo"
        vec = encode_indexable(svc, db.path, row[1], row[2], row[3], row[4],
                               vframes.get(pid) if mt == "video" else None)
        if vec is None:
            fail += 1
            continue
        db.conn.execute(
            "INSERT INTO photo_embeddings(photo_id, embedding, model, dim) VALUES (?,?,?,?) "
            "ON CONFLICT(photo_id) DO UPDATE SET embedding=excluded.embedding, "
            "model=excluded.model, dim=excluded.dim, created_at=datetime('now')",
            (pid, vec.astype(np.float32).tobytes(), MODEL_ID, int(vec.shape[0])),
        )
        ok += 1
        if i % args.commit_every == 0:
            db.conn.commit()
            el = time.perf_counter() - t0
            left = el / i * (len(rows) - i)
            print(f"  {i}/{len(rows)}  已用 {el:.0f}s  预计剩余 {left:.0f}s", flush=True)
    db.conn.commit()
    print(f"完成：成功 {ok} 张，失败 {fail} 张，用时 {time.perf_counter()-t0:.0f}s")
    db.close()
    return 0


def cmd_clip_search(args) -> int:
    """中文语义搜索（以文搜图）。"""
    import numpy as np
    from photo_manager.core.clip import MODEL_ID, get_service
    from photo_manager.core.db import Database

    svc = get_service(args.models)
    if not svc.available:
        print("未检测到 Chinese-CLIP 模型组件，缺少：" + "、".join(svc.missing_files()))
        print(f"请将模型文件放置于: {svc.dir}")
        return 1

    db = Database(args.db).connect()
    qv = svc.encode_text(args.query)

    # 分块计算，避免大库一次性载入全部向量
    scored: list[tuple[float, int]] = []
    chunk, last = 5000, 0
    while True:
        rows = db.conn.execute(
            "SELECT photo_id, embedding FROM photo_embeddings "
            "WHERE model = ? AND photo_id > ? ORDER BY photo_id LIMIT ?",
            (MODEL_ID, last, chunk),
        ).fetchall()
        if not rows:
            break
        last = rows[-1][0]
        mat = np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
        sims = mat @ qv          # 向量已 L2 归一化，点积即余弦相似度
        scored.extend(zip(sims.tolist(), [r[0] for r in rows]))

    if not scored:
        print("库中尚无语义向量，请先执行: pm clip-index")
        db.close()
        return 1

    scored.sort(key=lambda x: -x[0])
    top = scored[: args.limit]
    ids = [pid for _, pid in top]
    marks = ",".join("?" * len(ids))
    paths = {r[0]: r[1] for r in db.conn.execute(
        f"SELECT id, file_path FROM photos WHERE id IN ({marks})", ids)}

    print(f"共比对 {len(scored)} 张，最相关的 {len(top)} 张：")
    for sim, pid in top:
        print(f"  {sim:.3f}  {paths.get(pid, '(照片已移除)')}")
    db.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser(prog="pm")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest", help="扫描并入库")
    p.add_argument("root", nargs="+")
    p.set_defaults(func=cmd_ingest)
    p = sub.add_parser("faces", help="人脸检测与特征提取")
    p.add_argument("--models", default="models")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=0, help="并行进程数(0=自动)")
    p.set_defaults(func=cmd_faces)
    p = sub.add_parser("ocr", help="OCR 文本识别")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=0, help="并行进程数(0=自动)")
    p.set_defaults(func=cmd_ocr)
    p = sub.add_parser("events", help="事件时间聚类")
    p.add_argument("--gap", type=float, default=4.0, help="时间间隔阈值(小时)")
    p.set_defaults(func=cmd_events)
    p = sub.add_parser("facecluster", help="人脸聚类归一化")
    p.add_argument("--threshold", type=float, default=0.637, help="余弦相似度阈值")
    p.set_defaults(func=cmd_facecluster)
    p = sub.add_parser("search", help="FTS5 搜索（支持 tag:/person:/camera:/date:/gps: 等高级条件）")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--suggest", action="store_true")
    p.set_defaults(func=cmd_search)
    p = sub.add_parser("stats", help="库统计")
    p.set_defaults(func=cmd_stats)
    p = sub.add_parser("syncexport", help="导出元数据包（人物/事件/标签）")
    p.add_argument("--out", default="metadata_sync.meta.db")
    p.set_defaults(func=cmd_syncexport)
    p = sub.add_parser("syncimport", help="导入元数据包（导入前自动备份）")
    p.add_argument("file")
    p.set_defaults(func=cmd_syncimport)
    p = sub.add_parser("rethumb", help="重建缩略图（默认仅 RAW，修竖版方向；--all 全部）")
    p.add_argument("--all", action="store_true", help="重建全部照片的缩略图")
    p.set_defaults(func=cmd_rethumb)
    p = sub.add_parser("hashes", help="为照片计算感知哈希")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=0, help="并行进程数(0=自动)")
    p.set_defaults(func=cmd_hashes)
    p = sub.add_parser("dedupe", help="重复检测（仅报告）")
    p.add_argument("--dist", type=int, default=6, help="汉明距离阈值")
    p.add_argument("--show", type=int, default=10, help="显示前 N 组")
    p.set_defaults(func=cmd_dedupe)
    p = sub.add_parser("backup", help="在线备份数据库")
    p.add_argument("--out", default=None, help="备份目录")
    p.set_defaults(func=cmd_backup)
    p = sub.add_parser("tag", help="按路径匹配为照片打标签")
    p.add_argument("match")
    p.add_argument("tag")
    p.set_defaults(func=cmd_tag)
    p = sub.add_parser("restore", help="从备份恢复数据库")
    p.add_argument("file")
    p.set_defaults(func=cmd_restore)
    p = sub.add_parser("clip-index", help="生成中文语义向量（需 Chinese-CLIP 组件）")
    p.add_argument("--models", default="models")
    p.add_argument("--limit", type=int, default=None, help="仅处理前 N 张（调试用）")
    p.add_argument("--folder", default=None, help="仅处理路径包含该子串的照片")
    p.add_argument("--commit-every", type=int, default=200)
    p.set_defaults(func=cmd_clip_index)
    p = sub.add_parser("clip-search", help="中文语义搜索（以文搜图）")
    p.add_argument("query")
    p.add_argument("--models", default="models")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_clip_search)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
