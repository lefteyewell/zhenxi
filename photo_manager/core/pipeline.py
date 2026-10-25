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
"""入库管线：扫描 → 提取 → 缩略图 → 写库（增量续扫）。"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Callable, Iterable

from photo_manager.core import extractor
from photo_manager.core.db import Database
from photo_manager.core.scanner import FileInfo, Scanner

log = logging.getLogger(__name__)


class IngestPipeline:
    def __init__(self, db: Database, data_dir: str | Path, scanner: Scanner | None = None):
        self.db = db
        self.data_dir = Path(data_dir)
        self.thumbs_dir = self.data_dir / "thumbs"
        self.thumbs_dir.mkdir(parents=True, exist_ok=True)
        self.scanner = scanner or Scanner(db)

    def _thumb_path(self, file_path: str) -> Path:
        h = hashlib.sha1(file_path.encode("utf-8")).hexdigest()
        return self.thumbs_dir.resolve() / h[:2] / (h[2:16] + ".jpg")

    def ingest(
        self,
        roots: Iterable[str | Path],
        progress_cb: Callable[[int, int, str], None] | None = None,
        recursive: bool = True,
        copy_root: str | list[str] | None = None,
        register_roots: bool = True,
    ) -> dict:
        """扫描入库。recursive=False 只扫根目录自身（不含子文件夹）。

        copy_root 非空时（照片库根目录，可为单个或多个），把不在库内的照片
        先复制入库（多根时逐张挑选剩余空间足够的根，见 library.pick_copy_root；
        保持「源文件夹名/子路径」相对结构，只复制照片文件），再登记库内路径；
        源已在库内或复制失败 → 就地登记。见 core/library.py。
        register_roots=False 时不把 roots 写入 scan_roots 注册表
        （定时/检查类后台扫描用，避免污染「最近扫描位置」与扫描根列表）。
        """
        scan = self.scanner.scan(roots, progress_cb=progress_cb, recursive=recursive,
                                 register_roots=register_roots)
        files = scan.new_files + scan.changed_files
        changed_set = {f.file_path for f in scan.changed_files}
        relocated_src_map: dict[str, tuple[str, float, int]] = {}
        copy_roots = ([copy_root] if isinstance(copy_root, (str, os.PathLike))
                      else [r for r in (copy_root or []) if r])
        if copy_roots:
            from photo_manager.core.library import relocate_file

            anchors = [os.path.abspath(str(r)).replace("\\", "/") for r in (
                [roots] if isinstance(roots, (str, os.PathLike)) else roots)]
            known_src = {
                r[0].replace("\\", "/"): (r[1], r[2])
                for r in self.db.conn.execute(
                    "SELECT src_path, src_mtime, src_size FROM library_imports")
            }
            relocated: list[FileInfo] = []
            seen_dest: set[str] = set()
            for info in files:
                key = info.file_path.replace("\\", "/")
                if known_src.get(key) == (info.file_mtime, info.file_size):
                    continue  # 已复制入库且源未变化 → 跳过（库内已有登记）
                anchor = next(
                    (a for a in anchors
                     # 两侧都转小写：Windows 路径大小写不敏感，仅 anchor 转小写
                     # 会导致匹配恒为 False（盘符大写），多根时恒回退 anchors[0]
                     if key.lower().startswith(a.lower().rstrip("/") + "/")),
                    anchors[0] if anchors else os.path.dirname(info.file_path),
                )
                final = relocate_file(info.file_path, anchor, copy_roots)
                if final != info.file_path and final in seen_dest:
                    continue  # 多个源映射到同一目标（异常场景），只登记一次
                seen_dest.add(final)
                if final != info.file_path:
                    # 先用「原路径」清理 changed_set，再重赋 info；
                    # 重赋后 info.file_path 是库内新路径，本就不在集合里
                    changed_set.discard(info.file_path)
                    info = FileInfo(
                        file_path=final.replace("\\", "/"),
                        file_name=os.path.basename(final),
                        folder_path=os.path.dirname(final).replace("\\", "/"),
                        ext=os.path.splitext(final)[1].lower(),
                        file_size=info.file_size,
                        file_mtime=info.file_mtime,
                    )
                    relocated_src_map[info.file_path.replace("\\", "/")] = (
                        key, info.file_mtime, info.file_size)
                else:
                    # 复制失败回退就地登记：删除可能存在的旧映射，避免源被误跳过
                    self.db.conn.execute(
                        "DELETE FROM library_imports WHERE src_path=?", (key,))
                relocated.append(info)
            files = relocated
        total = len(files)
        t0 = time.perf_counter()
        stats = {"new": len(scan.new_files), "changed": len(scan.changed_files),
                 "indexed": 0, "failed": 0, "scan_sec": round(scan.duration, 2)}
        conn = self.db.conn
        # 恢复的文件：曾被 reindexCheck 标记 missing、现已重新出现的照片，
        # 扫描器只解除 missing（→pending），此处需走重索引闭环（元数据/缩略图/状态）。
        pending_rows = conn.execute(
            "SELECT file_path FROM photos WHERE status='pending'"
        ).fetchall()
        seen = {f.file_path for f in files}
        for (path,) in pending_rows:
            if path in seen or not os.path.exists(path):
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            files.append(FileInfo(
                file_path=path,
                file_name=os.path.basename(path),
                folder_path=os.path.dirname(path).replace("\\", "/"),
                ext=os.path.splitext(path)[1].lower(),
                file_size=st.st_size,
                file_mtime=st.st_mtime,
            ))
            changed_set.add(path)

        # 追加了 pending 恢复文件后总数会变，必须重算，否则进度回调里
        # i 会超过 total（进度条越过 100%）。
        total = len(files)

        for i, info in enumerate(files, 1):
            meta, thumb = self._process(info, force_thumb=info.file_path in changed_set)
            if meta is not None:
                self._upsert(info, meta, thumb)
                stats["indexed"] += 1
                src_rec = relocated_src_map.get(info.file_path.replace("\\", "/"))
                if src_rec is not None:
                    self.db.conn.execute(
                        "INSERT OR REPLACE INTO library_imports"
                        "(src_path, dest_path, src_mtime, src_size) VALUES (?,?,?,?)",
                        (src_rec[0], info.file_path, src_rec[1], src_rec[2]),
                    )
            else:
                conn.execute(
                    "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
                    " file_mtime, status, error) VALUES (?,?,?,?,?,?,?,?)",
                    (info.file_path, info.file_name, info.folder_path, info.ext,
                     info.file_size, info.file_mtime, "failed", "extract error"),
                )
                stats["failed"] += 1
            if i % 100 == 0 or i == total:
                # 0.5.67：i == total 也触发——重复导入时新文件很少（甚至 0 个），
                # 原先凑不满 100 一次回调都不发，进度弹窗停在第 1 张（用户反馈）。
                conn.commit()
                if progress_cb:
                    progress_cb(i, total, info.file_path)
        conn.commit()
        if total == 0 and progress_cb:
            progress_cb(0, 0, "")  # 全部跳过：发一次空进度让弹窗收起
        stats["ingest_sec"] = round(time.perf_counter() - t0, 2)
        return stats

    def _process(self, info, force_thumb: bool = False):
        """返回 (meta, thumb_path)；提取失败返回 (None, None)。
        force_thumb=True 时即使旧缩略图存在也重新生成（文件内容已变化）。

        0.5.51：thumbnail_path 改存**相对路径**（"thumbs/hh/hhh.jpg"，相对
        数据目录）——原先存绝对路径，程序目录一移动/改名（便携软件常态）
        全库缩略图断链成空白格；相对存储 + bridge 侧解析随库走。
        """
        thumb_path = self._thumb_path(info.file_path)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            meta = extractor.extract_metadata(info.file_path)
        except Exception:
            return None, None
        if meta["taken_at"] is None:
            meta["taken_at"] = time.strftime("%Y-%m-%dT%H:%M:%S",
                                             time.localtime(info.file_mtime))
        thumb = None
        if force_thumb and thumb_path.exists():
            try:
                thumb_path.unlink()
            except OSError:
                pass
        if not thumb_path.exists():
            size = extractor.make_thumbnail(info.file_path, thumb_path)
            if size:
                meta["thumb_width"], meta["thumb_height"] = size
        else:
            try:
                from PIL import Image

                with Image.open(thumb_path) as im:
                    meta["thumb_width"], meta["thumb_height"] = im.size
            except Exception:
                pass
        if thumb_path.exists():
            thumb = self._thumb_rel(thumb_path)
        return meta, thumb

    def _thumb_rel(self, thumb_path: Path) -> str:
        """绝对缩略图路径 → 相对数据目录的存储形式（thumbs/hh/hhh.jpg）。"""
        try:
            return thumb_path.resolve().relative_to(
                self.data_dir.resolve()).as_posix()
        except ValueError:
            # 极端情况（符号链接等导致不在数据目录下）：退回 basename 两段
            return f"thumbs/{thumb_path.parent.name}/{thumb_path.name}"

    def _store_keyframes(self, photo_id: int, file_path: str) -> None:
        """0.5.51：视频关键帧抽取落库（video_frames 表 + data/frames/）。

        路径同样相对数据目录存储（frames/<hash15>/frame_NN.jpg）——随库
        整体移动不失效。抽帧失败/非视频内容不写行（视频仍可缩略图与播放）。
        """
        try:
            import hashlib

            h = hashlib.sha1(file_path.encode("utf-8")).hexdigest()[:15]
            frame_dir = self.data_dir / "frames" / h
            names = extractor.extract_video_keyframes(file_path, frame_dir)
            self.db.conn.execute(
                "DELETE FROM video_frames WHERE photo_id=?", (photo_id,))
            for i, name in enumerate(names, 1):
                self.db.conn.execute(
                    "INSERT INTO video_frames(photo_id, idx, path) VALUES (?,?,?)",
                    (photo_id, i, f"frames/{h}/{name}"))
        except Exception:
            log.exception("视频关键帧抽取失败：%s", file_path)

    def _upsert(self, info, meta, thumb_path: str | None) -> None:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        existing = self.db.conn.execute(
            "SELECT id FROM photos WHERE file_path=?", (info.file_path,)
        ).fetchone()
        is_vid = meta.get("media_type") == "video"
        cols = [
            "file_name", "folder_path", "ext", "file_size", "file_mtime",
            "taken_at", "sort_key", "camera_make", "camera_model", "lens_model", "exposure",
            "f_number", "iso", "focal_length", "gps_lat", "gps_lon", "gps_alt",
            "width", "height", "thumbnail_path", "thumb_width", "thumb_height",
            "status", "error", "indexed_at", "media_type", "duration",
            "video_codec", "face_done", "ocr_done", "decode_error",
        ]
        vals = [
            info.file_name, info.folder_path, info.ext, info.file_size, info.file_mtime,
            meta["taken_at"], meta["taken_at"] or "", meta["camera_make"], meta["camera_model"], meta["lens_model"],
            meta["exposure"], meta["f_number"], meta["iso"], meta["focal_length"],
            meta["gps_lat"], meta["gps_lon"], meta["gps_alt"], meta["width"], meta["height"],
            thumb_path, meta.get("thumb_width"), meta.get("thumb_height"),
            "indexed", None, now, meta.get("media_type", "photo"), meta.get("duration"),
            meta.get("video_codec"), 1 if is_vid else 0, 1 if is_vid else 0, 0,
        ]
        if existing:
            pid = existing[0]
            self.db.conn.execute("DELETE FROM ocr_fts WHERE rowid=?", (pid,))
            self.db.conn.execute("DELETE FROM faces WHERE photo_id=?", (pid,))
            self.db.conn.execute("DELETE FROM ocr_texts WHERE photo_id=?", (pid,))
            # 图片内容已变化：旧语义向量必须清除。clip-index 是增量逻辑
            # （LEFT JOIN ... WHERE e.photo_id IS NULL），不删则该照片永不重算，
            # 语义搜索/以图搜图会继续用旧图的向量得出错误结果。
            self.db.conn.execute("DELETE FROM photo_embeddings WHERE photo_id=?", (pid,))
            # 视频不做人脸/OCR/语义：face_done/ocr_done 由下方 set_clause 置 1（is_vid），
            # 配合分析链 media_type='photo' 门禁形成双保险，杜绝视频被当图片解码而报错。
            self.db.conn.execute(
                "UPDATE photos SET face_count=0, has_text=0, ocr_text='' WHERE id=?",
                (pid,),
            )
            set_clause = ", ".join(f"{c}=?" for c in cols)
            self.db.conn.execute(
                f"UPDATE photos SET {set_clause} WHERE file_path=?",
                (*vals, info.file_path),
            )
        else:
            cols_sql = ", ".join(cols)
            marks = ", ".join("?" * len(cols))
            self.db.conn.execute(
                f"INSERT INTO photos(file_path, {cols_sql}) VALUES (?, {marks})",
                (info.file_path, *vals),
            )
            pid = self.db.conn.execute(
                "SELECT id FROM photos WHERE file_path=?", (info.file_path,)
            ).fetchone()[0]
        # 0.5.51：视频关键帧（按时长均匀抽 5 帧）——供 CLIP 编码进语义检索
        # 与信息面板帧带展示。只对新建/变更的视频重抽（_upsert 本就走这条路）。
        if is_vid:
            self._store_keyframes(pid, info.file_path)
