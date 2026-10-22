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
"""EXIF 提取 + 缩略图生成（Pillow + rawpy + exifread）。"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image, ImageOps

log = logging.getLogger(__name__)

# 0.5.43：注册现代图像编解码插件（导入副作用即登记进 Pillow 的全局解码器表）。
#   pillow-heif  → HEIC/HEIF（iPhone 默认）与 AVIF（新安卓）；HEIF 与 AVIF 需分别注册。
#   pillow_jxl_plugin → JPEG XL。
# 用 try/except 包裹：库缺失时优雅降级（这些格式打不开，但 JPEG/PNG/RAW 等不受影响），
# 绝不因缺一个可选解码库让整个 extractor 模块加载失败。
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    try:
        pillow_heif.register_avif_opener()  # AVIF 与 HEIF 是两套 opener，需显式注册
    except Exception:
        pass
except Exception:
    pass

try:
    import pillow_jxl_plugin  # noqa: F401  导入即注册 JPEG XL 解码
except Exception:
    pass

THUMB_MAX = 512

_TAG_MAKE = 271
_TAG_MODEL = 272
_TAG_DATETIME = 306
_TAG_EXPOSURE = 33434
_TAG_FNUMBER = 33437
_TAG_ISO = 34855
_TAG_DATETIME_ORIG = 36867
_TAG_DATETIME_DIGIT = 36868
_TAG_FOCAL = 37386
_TAG_LENS = 42036
_TAG_GPS = 34853
_IFD_EXIF = 34665

_GPS_LAT = 2
_GPS_LAT_REF = 1
_GPS_LON = 4
_GPS_LON_REF = 3
_GPS_ALT = 6


def _rational(v):
    if isinstance(v, tuple):
        num, den = v
        return num / den if den else None
    if hasattr(v, "numerator"):
        return v.numerator / v.denominator if v.denominator else None
    return float(v)


def _to_iso(s: str) -> str | None:
    s = s.strip()
    if not s:
        return None
    return s.replace(":", "-", 2).replace(" ", "T", 1)


def _gps_degrees(values, ref: str) -> float | None:
    if not values:
        return None
    deg, mn, sec = (_rational(v) for v in values[:3])
    if None in (deg, mn, sec):
        return None
    v = deg + mn / 60.0 + sec / 3600.0
    if ref in ("S", "W"):
        v = -v
    return round(v, 7)


# 受支持的全部相机 RAW 格式（与 core/scanner.py 保持一致）。
# 取自 LibRaw/dcraw 支持的相机 RAW 清单；排除通用栅格 .tif/.tiff（走 Pillow）
# 与极易误判的非相机 .raw。
_RAW_EXTS = {
    ".3fr", ".ari", ".arw", ".bay", ".bmq", ".cap", ".cin", ".cr2", ".cr3",
    ".crw", ".dc2", ".dcr", ".dcs", ".dng", ".drf", ".eip", ".erf", ".fff",
    ".gpr", ".iiq", ".k25", ".kdc", ".mdc", ".mef", ".mos", ".mrw", ".nef",
    ".nrw", ".obm", ".orf", ".pef", ".ptx", ".pxn", ".qtk", ".raf", ".rwl",
    ".rw2", ".rwz", ".sr2", ".srf", ".srw", ".sti", ".x3f",
}


def _thumb_is_jpeg(fmt) -> bool:
    """rawpy extract_thumb() 的格式是否为 JPEG。

    0.5.64 修复：rawpy 0.27 的 ThumbFormat 是普通 Enum（非 IntEnum），
    `fmt == 1` 恒为 False → make_preview 的内嵌预览分支从未生效，所有 RAW
    预览都在走慢速全图 postprocess，postprocess 一失败（截断/损坏文件）
    即无兜底 → 预览空白（缩略图正常，因 make_thumbnail 不检查 format）。
    兼容 IntEnum（==1）与普通 Enum（name=="JPEG"）两种形态。
    """
    if fmt is None:
        return False
    if fmt == 1:
        return True
    return getattr(fmt, "name", "") == "JPEG"

# 受支持的视频格式（0.5.44 V1，与 core/scanner.py 一致）。cv2 取帧 + 读时长/分辨率。
_VIDEO_EXTS = {
    ".mp4", ".m4v", ".mov", ".avi", ".mkv", ".wmv", ".asf", ".flv",
    ".f4v", ".webm", ".mpg", ".mpeg", ".mpe", ".mpv", ".3gp", ".3g2",
    ".3gpp", ".mts", ".m2ts", ".ts", ".ogv", ".vob",
}


def is_video(file_path: str | Path) -> bool:
    return Path(file_path).suffix.lower() in _VIDEO_EXTS


def _video_meta(p: str) -> dict:
    """视频元数据：分辨率 / 时长(秒) / 编码(FOURCC)。cv2 读不到创建时间，
    taken_at 由管线回退文件 mtime。"""
    import cv2  # noqa: PLC0415

    out = {"width": None, "height": None, "duration": None, "video_codec": None}
    cap = cv2.VideoCapture(p)
    if not cap.isOpened():
        return out
    try:
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if w and h:
            out["width"], out["height"] = int(w), int(h)
        if fps and frames and fps > 0:
            out["duration"] = round(float(frames) / float(fps), 3)
        fourcc = cap.get(cv2.CAP_PROP_FOURCC)
        if fourcc:
            codec = "".join(chr((int(fourcc) >> (8 * i)) & 0xFF) for i in range(4))
            out["video_codec"] = codec.strip("\x00").strip()
    except Exception as e:
        log.debug("video meta failed for %s: %s", p, e)
    finally:
        cap.release()
    return out


def make_video_thumbnail(file_path: str | Path, out_path) -> tuple[int, int] | None:
    """视频缩略图：取中段代表性帧编码 JPEG（避开可能的首黑帧/片尾），返回 (w, h)。"""
    import cv2  # noqa: PLC0415

    p = str(file_path)
    cap = cv2.VideoCapture(p)
    if not cap.isOpened():
        return None
    try:
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        frame = None
        if frames and frames > 1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frames * 0.5))
            ok, frame = cap.read()
            if not ok or frame is None:  # 中段 seek 失败→回到首帧
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
        else:
            ok, frame = cap.read()
        if frame is None:
            return None
        h, w = frame.shape[:2]
        m = max(w, h)
        if m > THUMB_MAX:  # 等比缩小，控缩略图体积
            s = THUMB_MAX / m
            frame = cv2.resize(frame, (max(1, int(w * s)), max(1, int(h * s))),
                               interpolation=cv2.INTER_AREA)
        ok, enc = cv2.imencode(".jpg", frame,
                               [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            return None
        with open(out_path, "wb") as f:
            f.write(enc.tobytes())
        hh, ww = frame.shape[:2]
        return (ww, hh)
    except Exception as e:
        log.debug("video thumbnail failed for %s: %s", p, e)
        return None
    finally:
        cap.release()


def extract_video_keyframes(file_path: str | Path, out_dir: str | Path,
                            n: int = 5, max_edge: int = 512) -> list[str]:
    """视频关键帧抽取（0.5.51：让视频进入语义检索）。

    按时长均匀取 n 帧（落在 10%~90% 区间，避开首黑帧/片尾），各自编码
    JPEG 存入 out_dir/frame_01.jpg …，返回**相对 out_dir**的文件名列表
    （调用方落库时再拼 data 相对路径）。抽不到帧返回 []。
    只读视频文件，不碰原片。
    """
    import cv2  # noqa: PLC0415

    p = str(file_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    cap = cv2.VideoCapture(p)
    if not cap.isOpened():
        return []
    try:
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not frames or frames < 2:
            frames = 0
        positions = []
        for i in range(1, n + 1):
            if frames:
                positions.append(int(frames * (0.1 + 0.8 * i / (n + 1))))
            else:
                positions.append(None)  # 帧数未知：顺序读前 n 帧
        for i, pos in enumerate(positions, 1):
            if pos is not None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, pos))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            h, w = frame.shape[:2]
            m = max(w, h)
            if m > max_edge:
                s = max_edge / m
                frame = cv2.resize(frame, (max(1, int(w * s)), max(1, int(h * s))),
                                   interpolation=cv2.INTER_AREA)
            name = f"frame_{i:02d}.jpg"
            ok, enc = cv2.imencode(".jpg", frame,
                                   [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                continue
            with open(out_dir / name, "wb") as f:
                f.write(enc.tobytes())
            names.append(name)
    except Exception as e:
        log.debug("video keyframes failed for %s: %s", p, e)
    finally:
        cap.release()
    return names


def _raw_exif(p: str) -> dict:
    """RAW 的 EXIF 提取。

    Pillow 打不开 RAW；exifread 也不认 CR3 这类 ISOBMFF 容器。
    通用做法：在文件内定位 TIFF 头（II*\0 / MM\0*）后从该偏移解析，
    对 CR3（偏移非 0）与 NEF/ARW/ORF 等 TIFF 系（偏移 0）都有效。
    尽力而为，任何异常都返回空 dict。
    """
    out: dict = {}
    try:
        import exifread

        with open(p, "rb") as f:
            data = f.read()

        # 1) 优先从文件头解析：RW2 / ORF / NEF / ARW 等 TIFF 系 exifread 可直接识别
        tags = {}
        try:
            tags = exifread.process_file(io.BytesIO(data), details=False)
        except Exception:
            tags = {}

        # 2) 拿不到厂商/型号时，退回定位 TIFF 头（CR3 等 ISOBMFF 容器的 TIFF 头不在开头）
        if "Image Make" not in tags and "Image Model" not in tags:
            for magic in (b"II*\x00", b"MM\x00*"):
                i = data.find(magic)
                if i > 0:
                    try:
                        tags = exifread.process_file(io.BytesIO(data[i:]), details=False)
                    except Exception:
                        pass
                    break
        if not tags:
            return out
        mapping = {
            "camera_make": "Image Make",
            "camera_model": "Image Model",
            "lens_model": "EXIF LensModel",
            "taken_at": "EXIF DateTimeOriginal",
            "exposure": "EXIF ExposureTime",
            "iso": "EXIF ISOSpeedRatings",
            "f_number": "EXIF FNumber",
            "focal_length": "EXIF FocalLength",
        }
        for key, tag in mapping.items():
            if tag not in tags:
                continue
            v = str(tags[tag]).strip()
            if not v:
                continue
            if key == "taken_at":
                v = _to_iso(v)
            elif key == "iso":
                try:
                    v = int(float(v))
                except ValueError:
                    continue
            elif key in ("f_number", "focal_length"):
                try:
                    v = float(v)
                except ValueError:
                    continue
            if v is not None:
                out[key] = v
    except Exception:
        pass
    return out


def extract_metadata(file_path: str | Path) -> dict:
    """返回 EXIF 元数据 dict（不存在字段为 None）。"""
    p = str(file_path)
    meta = {
        "taken_at": None, "camera_make": None, "camera_model": None,
        "lens_model": None, "exposure": None, "f_number": None,
        "iso": None, "focal_length": None,
        "gps_lat": None, "gps_lon": None, "gps_alt": None,
        "width": None, "height": None,
        "media_type": "video" if is_video(p) else "photo",
        "duration": None, "video_codec": None,
    }
    # 视频（0.5.44 V1）：cv2 读分辨率/时长/编码；taken_at 留空由管线回退文件 mtime；
    # 不走图片 EXIF，也无人脸/OCR/语义（分析链按 media_type 门禁跳过）。
    if meta["media_type"] == "video":
        meta.update(_video_meta(p))
        return meta
    exif = None
    exif_ifd = {}
    gps_ifd = {}
    try:
        with Image.open(p) as im:
            exif = im.getexif()
            meta["width"], meta["height"] = im.size
            if 34665 in exif:
                try:
                    exif_ifd = exif.get_ifd(34665)
                except Exception:
                    pass
            if 34853 in exif:
                try:
                    gps_ifd = exif.get_ifd(34853)
                except Exception:
                    pass
    except Exception:
        pass

    if exif_ifd:
        if 36867 in exif_ifd:
            meta["taken_at"] = _to_iso(str(exif_ifd[36867]))
        if not meta["taken_at"] and 36868 in exif_ifd:
            meta["taken_at"] = _to_iso(str(exif_ifd[36868]))
        meta["lens_model"] = str(exif_ifd[42036]) if 42036 in exif_ifd else None
        if 33434 in exif_ifd:
            v = _rational(exif_ifd[33434])
            if v:
                meta["exposure"] = f"1/{round(1 / v)}" if v < 1 else str(round(v))
        if 33437 in exif_ifd:
            meta["f_number"] = _rational(exif_ifd[33437])
        if 34855 in exif_ifd:
            try:
                meta["iso"] = int(exif_ifd[34855])
            except (TypeError, ValueError):
                pass
        if 37386 in exif_ifd:
            meta["focal_length"] = _rational(exif_ifd[37386])

    if exif:
        if not meta["taken_at"] and 306 in exif:
            meta["taken_at"] = _to_iso(str(exif[306]))
        meta["camera_make"] = str(exif[271]) if 271 in exif else None
        meta["camera_model"] = str(exif[272]) if 272 in exif else None

    if gps_ifd:
        meta["gps_lat"] = _gps_degrees(gps_ifd.get(2), str(gps_ifd.get(1, "N")))
        meta["gps_lon"] = _gps_degrees(gps_ifd.get(4), str(gps_ifd.get(3, "E")))
        if 6 in gps_ifd:
            alt = _rational(gps_ifd[6])
            if alt is not None:
                meta["gps_alt"] = round(alt, 2)

    if Path(p).suffix.lower() in _RAW_EXTS or meta["width"] is None:
        for k, v in _raw_exif(p).items():
            if meta.get(k) is None and v is not None:
                meta[k] = v

    if meta["width"] is None or meta["width"] == 0:
        try:
            import rawpy  # noqa: PLC0415

            with rawpy.imread(p) as raw:
                meta["width"], meta["height"] = raw.sizes.width, raw.sizes.height
        except Exception:
            pass
    return meta


def _to_rgb(im: "Image.Image") -> "Image.Image":
    """JPEG 不支持 RGBA/P 模式，先转 RGB（避免 save 抛 OSError）。"""
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    return im


_IMAGEMAGICK: str | None = None  # None=未探测；""=不可用；否则为可执行名


def _find_imagemagick() -> str | None:
    """探测 ImageMagick CLI（v7 的 `magick` 优先，回退 v6 的 `convert`）。

    关键陷阱：Windows 自带 `C:\\Windows\\System32\\convert.exe` 是「FAT→NTFS 磁盘
    转换」工具，与 ImageMagick v6 的 `convert` 同名。必须跑 `-version` 校验输出含
    "ImageMagick"，否则会把系统 convert.exe 误判成 ImageMagick（调用即失败）。
    """
    global _IMAGEMAGICK
    if _IMAGEMAGICK is None:
        import shutil  # noqa: PLC0415
        import subprocess  # noqa: PLC0415

        _IMAGEMAGICK = ""
        for name in ("magick", "convert"):
            path = shutil.which(name)
            if not path:
                continue
            try:
                r = subprocess.run([path, "-version"], capture_output=True, timeout=10)
                out = (r.stdout or b"") + (r.stderr or b"")
                if b"ImageMagick" in out:
                    _IMAGEMAGICK = name
                    break
            except Exception:
                continue
    return _IMAGEMAGICK or None


def imagemagick_available() -> bool:
    """供 scanner 判断是否纳入 ImageMagick 兜底格式。"""
    return _find_imagemagick() is not None


def imagemagick_to_jpeg(src: str, dst: str, max_edge: int = 1920) -> bool:
    """用 ImageMagick CLI 把 src 转成 JPEG（FITS/HDR/EXR 等 Pillow 解不了的格式）。
    成功返回 True。"""
    exe = _find_imagemagick()
    if exe is None:
        return False
    import subprocess  # noqa: PLC0415

    try:
        r = subprocess.run(
            [exe, src, "-resize", f"{max_edge}x{max_edge}>", "-quality", "88", dst],
            capture_output=True, timeout=120)
        return r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 200
    except Exception:
        return False


# Qt 图像插件可直接解码的格式（大图查看直接用原文件，无需生成预览）。
# 其余格式（44 种相机 RAW + HEIC/HEIF/AVIF/JXL + ImageMagick 兜底格式）
# 必须走 make_preview 解码——Qt QImage 读它们直接返回 null（查看器空白）。
QT_NATIVE_EXTS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".mpo",
}

PREVIEW_MAX_EDGE = 1920


def make_preview(file_path: str | Path, out_path: str | Path,
                 max_edge: int = PREVIEW_MAX_EDGE) -> tuple[int, int] | None:
    """生成大图查看用预览 JPEG（兼容旧签名，见 make_preview_ex）。"""
    r = make_preview_ex(file_path, out_path, max_edge)
    return None if r is None else (r[0], r[1])


def make_preview_ex(file_path: str | Path, out_path: str | Path,
                    max_edge: int = PREVIEW_MAX_EDGE,
                    ) -> tuple[int, int, str] | None:
    """生成大图查看用预览 JPEG，并报告解码可信度（0.5.64 损坏文件标记用）。

    为什么需要：QML Image 走 Qt 图像插件，只认 jpg/png/webp/tiff 等；
    相机 RAW（LibRaw 的 44 种）、iPhone HEIC、AVIF、FITS/HDR/EXR 等
    Qt 一律解不出 → 查看器空白（缩略图却正常，因为缩略图走本模块）。
    本函数按格式分层解码成 ≤max_edge 的 JPEG：
      1. RAW：优先内嵌预览（JPEG 且 ≥1024px），否则 rawpy 全图后处理 half_size；
      2. 其余：Pillow（含 pillow-heif 注册的 HEIF/AVIF opener）；
      3. Pillow 失败且系统装有 ImageMagick → CLI 兜底；
      4. 全部失败 → None（调用方显示"无法预览"占位，绝不崩）。

    返回 (w, h, state) 或 None。state 三值：
      "ok"        全图解码成功（可信）
      "unverified" RAW 走了内嵌预览快速路径，全图未验证（非损坏证据）
      "fallback"  全图解码失败，用内嵌/兜底图顶上——文件很可能损坏，
                  调用方（bridge photoViewUrl）据此写 photos.decode_error=1
    只读源文件，不碰原图。
    """
    p = str(file_path)
    ext = Path(p).suffix.lower()
    img = None
    state = "ok"
    small_emb = None  # 0.5.64：内嵌 JPEG 兜底（<1024px 也好过空白）
    try:
        if ext in _RAW_EXTS:
            import rawpy  # noqa: PLC0415

            with rawpy.imread(p) as raw:
                # 1) 内嵌预览（快；多数相机 ≥1024px 才值得用）。
                #    注意：走此路径时全图未验证 → state="unverified"（非损坏证据，
                #    深度解码检查负责补验）；仅当后处理失败退回内嵌图时才 state="fallback"。
                try:
                    from PIL import Image as _PilImage

                    thumb = raw.extract_thumb()
                    if _thumb_is_jpeg(getattr(thumb, "format", None)) and thumb.data:
                        emb = _PilImage.open(io.BytesIO(thumb.data))
                        # 0.5.64：内嵌 JPEG 可能带 EXIF Orientation（竖拍横存），
                        # 先转正再判定尺寸，否则预览方向错（缩略图同理，见下）
                        emb = ImageOps.exif_transpose(emb)
                        if max(emb.size) >= 1024:
                            img = emb
                            state = "unverified"
                        else:
                            small_emb = emb
                except Exception:
                    img = None
                # 2) 全图后处理（无内嵌预览或预览太小）
                if img is None:
                    try:
                        rgb = raw.postprocess(use_camera_wb=True, half_size=True)
                        img = Image.fromarray(rgb)
                        state = "ok"
                    except Exception:
                        # 0.5.64：postprocess 失败（截断/损坏 RAW：LibRawIOError 等）
                        # → 回退任意尺寸的内嵌 JPEG（缩略图同源，必可解码）
                        img = small_emb
                        small_emb = None
                        if img is None:
                            raise
                        state = "fallback"
        else:
            with Image.open(p) as im:
                im = ImageOps.exif_transpose(im)
                img = im
            state = "ok"
    except Exception:
        img = None
    if img is None:
        # 3) ImageMagick 兜底（FITS/HDR/EXR/FLIF/BPG/PCD…）——成功即真解码
        if imagemagick_to_jpeg(p, str(out_path), max_edge):
            try:
                with Image.open(out_path) as im:
                    return im.size[0], im.size[1], "ok"
            except Exception:
                return None
        return None
    try:
        img = _to_rgb(img)
        img.thumbnail((max_edge, max_edge))
        img.save(out_path, "JPEG", quality=88, optimize=True, progressive=True)
        return img.size[0], img.size[1], state
    except Exception:
        log.debug("preview save failed for %s", p, exc_info=True)
        return None


def decodable_extra_exts() -> set[str]:
    """返回当前环境「真正能解码」的扩展图片格式集合。

    含：现代编解码（HEIC/HEIF=iPhone 默认、AVIF=新安卓、JXL）+ ImageMagick 兜底
    格式（FITS/HDR/EXR/PhotoCD…）。scanner 用它扩充 IMAGE_EXTS——只纳入确实
    可解码的格式，从根上避免「白名单收录却生成不了缩略图」的静默坏图
    （HEIC 曾因只加白名单、未接解码库而踩过这个坑）。
    """
    exts: set[str] = set()
    try:
        import pillow_heif  # noqa: F401

        exts |= {".heic", ".heif", ".avif"}
    except Exception:
        pass
    try:
        import pillow_jxl_plugin  # noqa: F401

        exts.add(".jxl")
    except Exception:
        pass
    if _find_imagemagick():
        exts |= {".hdr", ".exr", ".fits", ".flif", ".bpg", ".jbig", ".jbg", ".pcd"}
    return exts


def _imagemagick_thumbnail(p: str, out_path) -> tuple[int, int] | None:
    """ImageMagick CLI 兜底：Pillow/rawpy 都打不开的冷门栅格转 JPEG 缩略图。

    覆盖 FITS(天文)/FLIF/BPG/JBIG/PhotoCD/HDR(Radiance)/OpenEXR 等，
    对齐 digiKam 的「原生 loader → ImageMagick」分层。未装 IM 则返回 None。
    """
    exe = _find_imagemagick()
    if not exe:
        return None
    import subprocess  # noqa: PLC0415

    try:
        # [0] 取首帧（FITS/PCD 可能多帧）；thumbnail '>' 只缩不放；strip 去元数据控体积；
        # 强制 jpg: 前缀，避免扩展名推断落到别的编码器。
        cmd = [exe, p + "[0]", "-thumbnail", f"{THUMB_MAX}x{THUMB_MAX}>",
               "-quality", "82", "-strip", "jpg:" + str(out_path)]
        r = subprocess.run(cmd, capture_output=True, timeout=60)
        if r.returncode != 0:
            return None
        with Image.open(out_path) as im:
            return im.size
    except Exception as e:
        log.debug("imagemagick thumbnail failed for %s: %s", p, e)
        return None


def make_thumbnail(file_path: str | Path, out_path: str | Path) -> tuple[int, int] | None:
    """生成缩略图（视频取中段帧；RAW 走内嵌预览/全图后处理；其余图片走 Pillow→ImageMagick 兜底），返回 (w, h) 或 None。"""
    p = str(file_path)
    ext = Path(p).suffix.lower()
    try:
        if is_video(p):
            return make_video_thumbnail(p, out_path)
        if ext in _RAW_EXTS:
            import rawpy  # noqa: PLC0415

            try:
                with rawpy.imread(p) as raw:
                    buf: bytes | None = None
                    # 内嵌预览：必须是可信的有效图（部分机型会返回几十字节的
                    # 损坏 BITMAP 占位，PIL 打不开），过小一律当作无效走后处理。
                    try:
                        t = raw.extract_thumb()
                        # 0.5.64：按 name 判定 JPEG（rawpy 0.27 的 ThumbFormat
                        # 非 IntEnum，==1 恒 False）；BITMAP/其他格式跳过
                        if (t and getattr(t, "data", None)
                                and len(t.data) > 512
                                and _thumb_is_jpeg(getattr(t, "format", None))):
                            buf = t.data
                        elif t and getattr(t, "data", None) and len(t.data) > 512:
                            # 非 JPEG 内嵌（BITMAP 像素）：交 PIL 试着打开，
                            # 打不开就走后处理（保持旧行为的宽容度）
                            try:
                                Image.open(io.BytesIO(t.data)).verify()
                                buf = t.data
                            except Exception:
                                buf = None
                    except Exception:
                        buf = None
                    if buf is None:
                        # 无预览或预览损坏（部分 IIQ/FFF/RWZ、损坏内嵌图）：
                        # 退回 rawpy 全图后处理再编码为 JPEG。
                        try:
                            rgb = raw.postprocess(use_camera_wb=True, half_size=True)
                            import cv2  # noqa: PLC0415

                            ok, enc = cv2.imencode(
                                ".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                            buf = enc.tobytes() if ok else None
                        except Exception:
                            buf = None
                    if buf is None:
                        return None
                    try:
                        with Image.open(io.BytesIO(buf)) as im:
                            # 0.5.64：内嵌 JPEG 可能带 EXIF Orientation（竖拍横存，
                            # 实测 Sony ARW ori=8）——不转正则缩略图横着显示
                            im = ImageOps.exif_transpose(im)
                            im = _to_rgb(im)
                            im.thumbnail((THUMB_MAX, THUMB_MAX))
                            im.save(out_path, "JPEG", quality=82,
                                    optimize=True, progressive=True)
                            return im.size
                    except Exception:
                        return None
            except Exception as e:
                log.debug("raw thumbnail failed for %s: %s", p, e)
                return None
        else:
            try:
                with Image.open(p) as im:
                    # JPEG 先 draft 预降采样，避免超大图全量解码的内存峰值
                    try:
                        if im.format == "JPEG":
                            im.draft("RGB", (THUMB_MAX, THUMB_MAX))
                    except Exception:
                        pass
                    im = ImageOps.exif_transpose(im)
                    im = _to_rgb(im)
                    im.thumbnail((THUMB_MAX, THUMB_MAX))
                    im.save(out_path, "JPEG", quality=82, optimize=True, progressive=True)
                    return im.size
            except Exception as e:
                # Pillow 打不开（冷门栅格：FITS/FLIF/BPG/HDR/EXR/PhotoCD…）
                # → ImageMagick CLI 兜底（对齐 digiKam 分层加载）。
                log.debug("pillow thumbnail failed for %s: %s (fallback ImageMagick)", p, e)
                return _imagemagick_thumbnail(p, out_path)
    except Exception as e:
        log.debug("thumbnail failed for %s: %s", p, e)
        return None
