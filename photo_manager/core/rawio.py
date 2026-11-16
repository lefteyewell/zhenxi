# PhotoManager - 照片管理系统
# Copyright (C) 2026 蒙汗药
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 (the License), or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""相机 RAW 统一读图入口（供人脸 / OCR 等 cv2 系分析管线复用）。

问题背景：OpenCV 的 imdecode 只认常规栅格，对相机 RAW 要么返回 None
（ARW/CR3/DNG/ORF/PEF/RAF/RW2/SRW 等），要么侥幸解出内嵌的百像素级
缩略图（CR2/NEF），导致人脸检测永久失败或「已分析但零人脸」。
本模块把 RAW 解码集中到一处，返回与 cv2.imdecode 语义一致的 BGR 数组
（**不应用 EXIF 旋转**，方向由 orientation() 单独给出，调用方按需转正），
使各分析管线拿到足够分辨率的图，且各品牌扩展名一视同仁。

设计取舍：
- 优先 RAW 内嵌 JPEG 预览（通常 1024~2000px，比全图后处理快一个量级），
  够 YuNet / RapidOCR 使用；无内嵌预览或预览不可解时回退
  rawpy.postprocess(half_size=True)，仍远优于百像素缩略图。
- 与 extractor.py 的缩略图/预览、clip.py 的语义向量同套 LibRaw 能力，
  但本模块只做「读成 ndarray」，不生成文件、不改库、不碰原图。
- RAW_EXTS 与 scanner/extractor/clip/library_bridge 四处集合保持逐项一致
  （tests/test_raw_image.py 有断言）。刻意不含通用后缀 .raw：scanner.py
  已注明「极易误判的非相机 .raw（通用二进制常以此后缀）」，保持一致。
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np

# 受支持的全部相机 RAW 格式（LibRaw/dcraw 清单，覆盖各厂商各代机型）。
# 新增品牌/新扩展名时，务必同步 scanner.RAW_EXTS、extractor._RAW_EXTS、
# clip.RAW_EXTS、library_bridge._HQ_SKIP_EXTS（测试会拦截不一致）。
RAW_EXTS = frozenset({
    ".3fr", ".ari", ".arw", ".bay", ".bmq", ".cap", ".cin", ".cr2", ".cr3",
    ".crw", ".dc2", ".dcr", ".dcs", ".dng", ".drf", ".eip", ".erf", ".fff",
    ".gpr", ".iiq", ".k25", ".kdc", ".mdc", ".mef", ".mos", ".mrw", ".nef",
    ".nrw", ".obm", ".orf", ".pef", ".ptx", ".pxn", ".qtk", ".raf", ".rwl",
    ".rw2", ".rwz", ".sr2", ".srf", ".srw", ".sti", ".x3f",
})


# RAW 读图层版本：仅当「解码方式的变更会让既有分析结果失效」时 +1。
# 数据库的 meta.raw_reader_version 记录上次迁移版本，低于此值时由
# core/db.py::_migrate_raw_analysis_state 自动把历史 RAW 的人脸 / OCR 结果
# 作废一次。1 = 0.6.30：cv2 / RapidOCR 直读原图 → 统一走 LibRaw 读图。
RAW_READER_VERSION = 1


def is_raw(path: str | Path) -> bool:
    """按扩展名判断是否为相机 RAW（大小写不敏感）。"""
    return Path(str(path)).suffix.lower() in RAW_EXTS


# ---- TIFF 容器型 RAW（0.6.32）------------------------------------------------
# 背景：部分转换工具把 NEF/CR2/ARW 等传感器数据原样转存为 .tiff（TIFF 容器
# 装 RAW + 内嵌预览），扩展名不在 RAW_EXTS（.raw 同理的有意排除逻辑不适用，
# 这里是真实的相机 RAW），cv2/Pillow 只能解出百像素级内嵌缩略图甚至完全
# 解不出（TIFF 目录缺解码必需字段），而 LibRaw 按**内容**识别与扩展名无关。
# 实测样组：21 个 .tiff 里 10 个 cv2/PIL 全解不出、11 个只解出 120×160~
# 852×640 内嵌缩略图（真实 2608×1950~8000×5320）。
CONTAINER_SNIFF_EXTS = frozenset({".tif", ".tiff"})
_SNIFF_MIN_EDGE = 1024  # 普通解码结果最长边低于此值才值得嗅探
_sniff_cache: dict[str, tuple[float, int, bool]] = {}
_SNIFF_CACHE_MAX = 512


def is_container_raw(path: str | Path) -> bool:
    """扩展名不是 RAW、但按内容是相机 RAW（TIFF 容器，仅 .tif/.tiff）。

    判别标准（缺一不可，宁可漏判不可误判）：
      1. 扩展名 ∈ {.tif, .tiff}——其余扩展名不嗅探，正常库零开销；
      2. LibRaw 能按内容打开，且 sizes 明显大于 Pillow 读到的尺寸
         （≥2 倍，Pillow 打不开也算命中）——普通照片 TIFF 即使被 LibRaw
         误开，两者尺寸相同，不会被送去 demosaic。
    结果按 (路径, mtime, size) 缓存：人脸 / OCR / 预览 / 缩略图 / 元数据
    多条链路对同一文件共用一次嗅探，文件变化后自动失效。
    """
    p = str(path)
    if Path(p).suffix.lower() not in CONTAINER_SNIFF_EXTS:
        return False
    try:
        st = os.stat(p)
        stamp = (st.st_mtime, st.st_size)
    except OSError:
        return False
    hit = _sniff_cache.get(p)
    if hit is not None and (hit[0], hit[1]) == stamp:
        return hit[2]
    ok = _sniff_probe(p)
    if len(_sniff_cache) >= _SNIFF_CACHE_MAX:
        _sniff_cache.clear()
    _sniff_cache[p] = (stamp[0], stamp[1], ok)
    return ok


def _sniff_probe(p: str) -> bool:
    """实际嗅探：LibRaw 尺寸远大于 Pillow 尺寸（或 Pillow 打不开）即命中。"""
    pil_max = 0
    try:
        from PIL import Image  # noqa: PLC0415

        with Image.open(p) as im:
            pil_max = max(im.size)
    except Exception:
        pil_max = 0
    try:
        import rawpy  # noqa: PLC0415

        with rawpy.imread(p) as raw:
            s = raw.sizes
            raw_max = max(int(getattr(s, "width", 0) or 0),
                          int(getattr(s, "height", 0) or 0))
    except Exception:
        return False
    if raw_max <= 0:
        return False
    return pil_max == 0 or raw_max >= pil_max * 2


def read_bgr(path: str | Path) -> np.ndarray:
    """读图为 BGR ndarray；失败抛 ValueError（与旧 cv2 路径同语义）。

    普通图片走 np.fromfile + cv2.imdecode（兼容中文路径，行为不变）；
    RAW 走 rawpy：内嵌 JPEG 预览优先，回退半尺寸全图后处理。
    0.6.32 起普通分支解不出、或只解出 <1024px 的小图时，对 .tif/.tiff
    做 LibRaw 内容嗅探兜底（见 is_container_raw）——容器型相机 RAW 由此
    获得与真 RAW 同级的分辨率；真 TIFF（能解出大图）不触发，行为不变。
    返回的图**未应用 EXIF 旋转**（容器型 RAW 除外——它返回的已是正立
    图，orientation() 对其恒返回 1，调用方按 tag 再转会双转，实测 D3X）。
    """
    import cv2  # noqa: PLC0415

    p = str(path)
    if is_raw(p):
        img = _read_raw_bgr(p)
    else:
        img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
        if ((img is None or max(img.shape[:2]) < _SNIFF_MIN_EDGE)
                and is_container_raw(p)):
            sniffed = _read_container_bgr(p)
            if sniffed is not None:
                return sniffed
            # 嗅探读图失败（截断/损坏）：退回上面的普通解码结果（可能是
            # 小缩略图），宁小也不抛，避免照片永久滞留待分析队列。
    if img is None:
        raise ValueError(f"无法读取图片: {p}")
    return img


def _read_container_bgr(p: str) -> np.ndarray | None:
    """容器型 RAW 读图：内嵌预览（自带 EXIF 方向，先转正）→ 半尺寸全图。

    与 _read_raw_bgr 的两点差异：
    - 内嵌预览用 exif_transpose 按其**自带**的 EXIF 方向转正——容器外层
      TIFF 的 Orientation tag 与像素流方向不一致（实测 Nikon 容器外层
      tag=8、内嵌预览已正立），按外层 tag 转会把图转躺；
    - 全部失败返回 None（由调用方退回普通解码结果），不抛异常。
    """
    import cv2  # noqa: PLC0415
    import rawpy  # noqa: PLC0415

    small = None
    try:
        with rawpy.imread(p) as raw:
            try:
                thumb = raw.extract_thumb()
                fmt = getattr(thumb, "format", None)
                if getattr(fmt, "name", str(fmt)) == "JPEG" and thumb.data:
                    from PIL import Image, ImageOps  # noqa: PLC0415

                    with Image.open(io.BytesIO(thumb.data)) as im:
                        im = ImageOps.exif_transpose(im)
                        rgb = np.asarray(im.convert("RGB"))
                    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                    if max(rgb.shape[:2]) >= _SNIFF_MIN_EDGE:
                        return bgr
                    small = bgr
            except Exception:
                pass
            try:
                rgb = raw.postprocess(use_camera_wb=True, half_size=True)
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            except Exception:
                return small
    except Exception:
        return None


def _read_raw_bgr(p: str) -> np.ndarray:
    import cv2  # noqa: PLC0415
    import rawpy  # noqa: PLC0415

    with rawpy.imread(p) as raw:
        small = None
        # 1) 内嵌 JPEG 预览：快、尺寸通常足够（≥1024px）。
        #    rawpy 0.27 的 ThumbFormat 是普通 Enum，必须按 .name 判定，
        #    `fmt == 1` 恒 False（0.5.64 曾因此让预览快速路径整体失效）。
        try:
            thumb = raw.extract_thumb()
            fmt = getattr(thumb, "format", None)
            if getattr(fmt, "name", str(fmt)) == "JPEG" and thumb.data:
                from PIL import Image  # noqa: PLC0415

                with Image.open(io.BytesIO(thumb.data)) as im:
                    rgb = np.asarray(im.convert("RGB"))
                small = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                # 老机型的内嵌预览可能只有百像素级（实测 Olympus ORF
                # 120×160），喂给 YuNet 等于没检测 → 弃用走全图后处理。
                if max(rgb.shape[:2]) >= 1024:
                    return small
        except Exception:
            pass
        # 2) 无可用大预览 → 半尺寸全图后处理（输出 RGB）。
        try:
            rgb = raw.postprocess(use_camera_wb=True, half_size=True)
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception:
            # 3) 全图后处理失败（截断/损坏 RAW）：宁可退小预览也不抛异常，
            #    避免照片永久滞留待分析队列反复失败。
            if small is not None:
                return small
            raise


def orientation(path: str | Path) -> int:
    """读取 EXIF Orientation（0x0112），缺失/不可读返回 1。

    普通图片用 Pillow；RAW 的 Pillow 打不开，改用 exifread，并沿用
    extractor._raw_exif 的 TIFF 头搜索兜底（CR3 等 ISOBMFF 容器的
    TIFF 头不在文件开头）。
    """
    p = str(path)
    if not is_raw(p):
        # 0.6.32：容器型 RAW 由 read_bgr 返回的已是正立图（内嵌预览按自带
        # EXIF 转正 / LibRaw flip），外层 TIFF 的 Orientation tag 与像素流
        # 方向不一致（实测 Nikon 容器外层 tag=8、像素已正立），再按 tag 转
        # 会双转 → 恒返回 1，调用方不再旋转。
        if is_container_raw(p):
            return 1
        try:
            from PIL import Image  # noqa: PLC0415

            with Image.open(p) as im:
                return int(im.getexif().get(0x0112, 1))
        except Exception:
            return 1
    try:
        import exifread  # noqa: PLC0415

        with open(p, "rb") as f:
            data = f.read()
        tags = exifread.process_file(io.BytesIO(data), details=False)
        tag = tags.get("Image Orientation") or tags.get("EXIF Orientation")
        if tag is None:
            for magic in (b"II*\x00", b"MM\x00*"):
                i = data.find(magic)
                if i > 0:
                    tags = exifread.process_file(io.BytesIO(data[i:]), details=False)
                    tag = tags.get("Image Orientation") or tags.get("EXIF Orientation")
                    if tag is not None:
                        break
        if tag is None:
            return 1
        return int(getattr(tag, "values", [tag])[0])
    except Exception:
        return 1
