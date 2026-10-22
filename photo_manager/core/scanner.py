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
"""递归扫描照片文件：格式白名单、增量跟踪（mtime+size）。"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from photo_manager.core.db import Database

# Pillow 原生即可解码的图片格式（Pillow 必装，恒纳入）。
# 含通用格式 + 摄影师常用扩展：多图/3D(MPO)、Photoshop(PSD)、TGA/PCX/PNM 系。
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff",
    ".bmp", ".webp", ".gif",
    ".mpo", ".psd", ".tga", ".pcx", ".pnm", ".pbm", ".pgm", ".ppm",
}
# 现代编解码（HEIC/HEIF=iPhone 默认、AVIF=新安卓、JXL）与 ImageMagick 兜底格式
# （FITS/HDR/EXR/PhotoCD…）按当前环境能否真正解码动态纳入——只收编解得开的，
# 从根上避免「白名单收录却生成不了缩略图」的静默坏图（HEIC 曾因只加白名单踩过）。
try:
    from photo_manager.core.extractor import decodable_extra_exts as _extra_exts

    IMAGE_EXTS |= _extra_exts()
except Exception:
    pass
# 受支持的全部相机 RAW 格式（覆盖各主流厂商各代机型）。
# 取自 LibRaw/dcraw 支持的相机 RAW 清单；排除通用栅格格式 .tif/.tiff（已在
# IMAGE_EXTS 走 Pillow）与极易误判的非相机 .raw（通用二进制常以此后缀）。
RAW_EXTS = {
    ".3fr", ".ari", ".arw", ".bay", ".bmq", ".cap", ".cin", ".cr2", ".cr3",
    ".crw", ".dc2", ".dcr", ".dcs", ".dng", ".drf", ".eip", ".erf", ".fff",
    ".gpr", ".iiq", ".k25", ".kdc", ".mdc", ".mef", ".mos", ".mrw", ".nef",
    ".nrw", ".obm", ".orf", ".pef", ".ptx", ".pxn", ".qtk", ".raf", ".rwl",
    ".rw2", ".rwz", ".sr2", ".srf", ".srw", ".sti", ".x3f",
}
# 受支持的视频格式（0.5.44 V1 编目级）：cv2(OpenCV) 取中段帧出缩略图 +
# 读分辨率/fps/帧数得时长。取主流容器（opencv 内置 ffmpeg 后端可靠解码）；
# 暂不收 rm/rmvb/amv/dv 等解码不确定的老格式（避免白名单却出不了图）。
VIDEO_EXTS = {
    ".mp4", ".m4v", ".mov", ".avi", ".mkv", ".wmv", ".asf", ".flv",
    ".f4v", ".webm", ".mpg", ".mpeg", ".mpe", ".mpv", ".3gp", ".3g2",
    ".3gpp", ".mts", ".m2ts", ".ts", ".ogv", ".vob",
}
ALL_EXTS = IMAGE_EXTS | RAW_EXTS | VIDEO_EXTS

SKIP_DIRS = {".git", "__pycache__", "$recycle.bin", "system volume information"}


@dataclass
class FileInfo:
    file_path: str
    file_name: str
    folder_path: str
    ext: str
    file_size: int
    file_mtime: float


@dataclass
class ScanResult:
    new_files: list[FileInfo] = field(default_factory=list)
    changed_files: list[FileInfo] = field(default_factory=list)
    total_seen: int = 0
    dirs_seen: int = 0
    duration: float = 0.0


class Scanner:
    """增量扫描：仅返回新增或 mtime/size 变化的文件。"""

    def __init__(self, db: Database, exts: set[str] | None = None):
        self.db = db
        self.exts = exts or ALL_EXTS

    def scan(
        self,
        roots: Iterable[str | Path],
        progress_cb: Callable[[int, int, str], None] | None = None,
        recursive: bool = True,
        register_roots: bool = True,
    ) -> ScanResult:
        if isinstance(roots, (str, os.PathLike)):
            roots = [roots]
        roots = [os.path.abspath(str(r)).replace("\\", "/") for r in roots]
        result = ScanResult()
        t0 = time.perf_counter()

        # 先统计待扫文件数用于进度显示。此前把「新增+变化数」当总数传给回调，
        # 而 done 传的是已扫描数，进度条会出现 [1200/5] 这种错乱。
        # 这里只 walk 计数、不读文件，开销远小于后续入库。
        est_total = 0
        for r in roots:
            for dirpath, dirnames, filenames in self._iter_dirs(r, recursive):
                est_total += sum(
                    1 for n in filenames
                    if os.path.splitext(n)[1].lower() in self.exts
                )

        known = {
            row[0]: (row[1], row[2])
            for row in self.db.conn.execute(
                "SELECT file_path, file_mtime, file_size FROM photos"
            )
        }
        changed: dict[str, tuple[float, int]] = {}

        for root in roots:
            # 统一为绝对路径：避免相对/绝对根重复入库同一文件
            root = os.path.abspath(str(root)).replace("\\", "/")
            for info in self._walk(root, recursive):
                result.total_seen += 1
                key = info.file_path
                if key in known:
                    old_mtime, old_size = known[key]
                    if old_mtime == info.file_mtime and old_size == info.file_size:
                        continue
                    changed[key] = (info.file_mtime, info.file_size)
                    result.changed_files.append(info)
                else:
                    result.new_files.append(info)
                if progress_cb and result.total_seen % 200 == 0:
                    progress_cb(result.total_seen, max(est_total, result.total_seen),
                                info.file_path)

        # 恢复：磁盘上重新出现的照片（之前被 reindexCheck 标记 missing）——
        # 即使 mtime/size 未变也需解除 missing，否则会永久不可见。
        for (path,) in self.db.conn.execute(
            "SELECT file_path FROM photos WHERE status='missing'"
        ):
            abs_path = os.path.abspath(path).replace("\\", "/")
            if os.path.exists(abs_path):
                self.db.conn.execute(
                    "UPDATE photos SET status='pending', error=NULL WHERE file_path=?",
                    (path,),
                )
                result.changed_files.append(
                    FileInfo(
                        file_path=abs_path,
                        file_name=os.path.basename(abs_path),
                        folder_path=os.path.dirname(abs_path).replace("\\", "/"),
                        ext=os.path.splitext(abs_path)[1].lower(),
                        file_size=0,
                        file_mtime=0.0,
                    )
                )

        for key, (mtime, size) in changed.items():
            self.db.conn.execute(
                "UPDATE photos SET file_mtime=?, file_size=?, status='pending' WHERE file_path=?",
                (mtime, size, key),
            )
        if register_roots:
            for root in roots:
                root = os.path.abspath(str(root)).replace("\\", "/")
                self.db.conn.execute(
                    "INSERT OR REPLACE INTO scan_roots(path, last_scan_at) VALUES (?, ?)",
                    (root, time.strftime("%Y-%m-%d %H:%M:%S")),
                )
        self.db.commit()
        result.duration = time.perf_counter() - t0
        return result

    def _iter_dirs(self, root: str, recursive: bool = True):
        """目录遍历（供进度计数）：recursive=False 时只看根目录自身。"""
        if recursive:
            yield from os.walk(root)
        else:
            root = root.rstrip("/\\")
            if os.path.isdir(root):
                yield root, [], [e.name for e in os.scandir(root) if e.is_file()]

    def _walk(self, root: str, recursive: bool = True):
        if not recursive:
            root = root.rstrip("/\\")
            if os.path.isdir(root):
                for entry in os.scandir(root):
                    if not entry.is_file():
                        continue
                    info = self._file_info(entry.path)
                    if info is not None:
                        yield info
            return
        for dirpath, dirnames, filenames in os.walk(root):
            self._prune(dirnames)
            for name in filenames:
                full = os.path.join(dirpath, name).replace("\\", "/")
                info = self._file_info(full)
                if info is not None:
                    yield info

    def _file_info(self, full: str):
        """按扩展名白名单构造 FileInfo；非图片文件返回 None（不做任何读取）。"""
        ext = os.path.splitext(full)[1].lower()
        if ext not in self.exts:
            return None
        try:
            st = os.stat(full)
        except OSError:
            return None
        return FileInfo(
            file_path=full,
            file_name=os.path.basename(full),
            folder_path=os.path.dirname(full).replace("\\", "/"),
            ext=ext,
            file_size=st.st_size,
            file_mtime=st.st_mtime,
        )

    @staticmethod
    def _prune(dirnames: list[str]) -> None:
        keep = []
        for d in dirnames:
            if d[0] in (".", "~") or d.lower() in SKIP_DIRS:
                continue
            keep.append(d)
        dirnames[:] = keep
