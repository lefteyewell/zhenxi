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
"""测试图集生成工具（阶段 0）

生成模拟照片集，覆盖以下场景：
- 多品牌相机 EXIF（索尼 / 佳能 / 尼康 / 富士，不同镜头与参数）
- 多文件夹结构（模拟多个会议/活动事件，多相机分文件夹）
- 少量照片含横幅文字（供 OCR 测试）
- 部分照片含模拟人脸（供人脸流水线测试，真实人脸待用户提供）
- 混合分辨率与宽高比

用法:
    python tools/gen_test_images.py [--count N] [--out test_data]
"""
import argparse
import math
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

import piexif
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# 场景定义
# ---------------------------------------------------------------------------

EVENTS = [
    {
        "name": "2025-03-02_公司年会",
        "date": datetime(2025, 3, 2, 9, 30),
        "banner": "2025年度公司年会",
        "cameras": [
            {"folder": "sony_a7rm5", "make": "SONY", "model": "ILCE-7RM5",
             "lens": "FE 24-70mm F2.8 GM II", "prefix": "DSC0", "ext": ".ARW"},
            {"folder": "canon_r6m2", "make": "Canon", "model": "Canon EOS R6 Mark II",
             "lens": "RF70-200mm F2.8 L IS USM", "prefix": "_MG_", "ext": ".CR3"},
            {"folder": "nikon_z9", "make": "NIKON CORPORATION", "model": "NIKON Z 9",
             "lens": "NIKKOR Z 24-70mm f/2.8 S", "prefix": "_DSC", "ext": ".NEF"},
        ],
    },
    {
        "name": "2025-06-18_产品发布会",
        "date": datetime(2025, 6, 18, 14, 0),
        "banner": "新品发布会",
        "cameras": [
            {"folder": "sony_a7rm5", "make": "SONY", "model": "ILCE-7RM5",
             "lens": "FE 70-200mm F2.8 GM OSS II", "prefix": "DSC0", "ext": ".ARW"},
            {"folder": "fuji_xh2s", "make": "FUJIFILM", "model": "X-H2S",
             "lens": "XF16-55mmF2.8 R LM WR", "prefix": "DSCF", "ext": ".RAF"},
        ],
    },
    {
        "name": "2025-08-10_海边风景",
        "date": datetime(2025, 8, 10, 6, 45),
        "banner": None,
        "cameras": [
            {"folder": "canon_r6m2", "make": "Canon", "model": "Canon EOS R6 Mark II",
             "lens": "RF15-35mm F2.8 L IS USM", "prefix": "_MG_", "ext": ".CR3"},
        ],
    },
    {
        "name": "2025-09-15_人物写真",
        "date": datetime(2025, 9, 15, 16, 30),
        "banner": None,
        "cameras": [
            {"folder": "sony_a7rm5", "make": "SONY", "model": "ILCE-7RM5",
             "lens": "FE 85mm F1.4 GM", "prefix": "DSC0", "ext": ".ARW"},
            {"folder": "canon_r6m2", "make": "Canon", "model": "Canon EOS R6 Mark II",
             "lens": "RF85mm F1.2 L USM", "prefix": "_MG_", "ext": ".CR3"},
        ],
    },
]

SIZES = [
    (6000, 4000), (6000, 3376), (4000, 6000), (6720, 4480), (4000, 3000),
]
ISOS = [100, 200, 400, 800, 1600, 3200]
APERTURES = [1.4, 1.8, 2.8, 4.0, 5.6, 8.0]
SHUTTERS = [(1, 60), (1, 125), (1, 250), (1, 500), (1, 1000), (1, 2000)]

# ---------------------------------------------------------------------------
# 图像合成
# ---------------------------------------------------------------------------


def _banner_font(size: int):
    """尽力寻找中文字体，找不到则退回默认。"""
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _random_scene(size, seed):
    """生成带渐变的模拟场景背景。"""
    w, h = size
    rnd = random.Random(seed)
    r1 = rnd.randint(0, 255)
    g1 = rnd.randint(0, 255)
    b1 = rnd.randint(0, 255)
    base = Image.new("RGB", (w, h), (r1, g1, b1))
    draw = ImageDraw.Draw(base)
    # 天空感渐变 + 随机色块
    for i in range(12):
        x0 = rnd.randint(-w // 3, w - 200)
        y0 = rnd.randint(-h // 3, h - 200)
        x1 = x0 + rnd.randint(150, 700)
        y1 = y0 + rnd.randint(150, 700)
        c = (rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255))
        draw.ellipse([x0, y0, x1, y1], fill=c)
    base = base.filter(ImageFilter.GaussianBlur(60))
    # 少量纹理点
    for _ in range(60):
        x = rnd.randint(0, w - 1)
        y = rnd.randint(0, h - 1)
        s = rnd.randint(2, 10)
        c = (rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255))
        draw.ellipse([x, y, x + s, y + s], fill=c)
    return base


def _draw_banner(img, text):
    """在图像上部绘制横幅文字（模拟会议横幅/PPT）。"""
    w, h = img.size
    draw = ImageDraw.Draw(img)
    font = _banner_font(max(40, h // 14))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    bar_h = th + 40
    draw.rectangle([0, 0, w, bar_h], fill=(120, 20, 20, 255))
    draw.text(((w - tw) / 2, (bar_h - th) / 2 - bbox[1]), text,
              font=font, fill=(255, 255, 255))


def _draw_face(img, cx, cy, r, seed):
    """绘制简笔人脸（肤色椭圆 + 五官），用于人脸流水线占位测试。"""
    rnd = random.Random(seed)
    draw = ImageDraw.Draw(img)
    skin = (rnd.randint(200, 235), rnd.randint(150, 185), rnd.randint(120, 155))
    draw.ellipse((cx - r, cy - int(r * 1.2), cx + r, cy + int(r * 1.25)), fill=skin)
    # 头发
    draw.arc([cx - int(r * 1.05), cy - int(r * 1.4), cx + int(r * 1.05), cy - int(r * 0.4)],
             180, 360, fill=(40, 30, 25), width=max(6, r // 5))
    # 眼睛
    eye_y = cy - int(r * 0.2)
    draw.ellipse([cx - int(r * 0.45), eye_y, cx - int(r * 0.2), eye_y + int(r * 0.22)],
                 fill=(40, 35, 30))
    draw.ellipse([cx + int(r * 0.2), eye_y, cx + int(r * 0.45), eye_y + int(r * 0.22)],
                 fill=(40, 35, 30))
    # 嘴
    draw.arc([cx - int(r * 0.3), cy + int(r * 0.3), cx + int(r * 0.3), cy + int(r * 0.7)],
             0, 180, fill=(120, 60, 50), width=max(3, r // 8))


def _make_exif(make, model, lens, dt: datetime, iso, aperture, shutter, w, h):
    """构造 EXIF 数据。"""
    zeroth = {
        piexif.ImageIFD.Make: make.encode("utf-8"),
        piexif.ImageIFD.Model: model.encode("utf-8"),
        piexif.ImageIFD.Software: "Test Image Generator".encode("utf-8"),
    }
    exif = {
        piexif.ExifIFD.DateTimeOriginal: dt.strftime("%Y:%m:%d %H:%M:%S").encode(),
        piexif.ExifIFD.DateTimeDigitized: dt.strftime("%Y:%m:%d %H:%M:%S").encode(),
        piexif.ExifIFD.LensModel: lens.encode("utf-8"),
        piexif.ExifIFD.ISOSpeedRatings: iso,
        piexif.ExifIFD.FNumber: (int(aperture * 100), 100),
        piexif.ExifIFD.ExposureTime: (shutter[1], shutter[0]),
        piexif.ExifIFD.FocalLength: (4000, 100),
        piexif.ExifIFD.FocalLengthIn35mmFilm: 35,
        piexif.ExifIFD.ExifVersion: b"0231",
    }
    gps = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: ((39, 1), (54, 1), (30, 1)),
        piexif.GPSIFD.GPSLongitudeRef: b"E",
        piexif.GPSIFD.GPSLongitude: ((116, 1), (23, 1), (30, 1)),
    }
    first = {
        piexif.ImageIFD.XResolution: (300, 1),
        piexif.ImageIFD.YResolution: (300, 1),
    }
    return {"0th": zeroth, "Exif": exif, "GPS": gps, "1st": first}


def generate(out_dir: Path, count_per_camera: int):
    out_dir = Path(out_dir)
    rnd = random.Random(20260801)
    total = 0
    for event in EVENTS:
        for cam in event["cameras"]:
            cam_dir = out_dir / event["name"] / cam["folder"]
            cam_dir.mkdir(parents=True, exist_ok=True)
            t = event["date"]
            for i in range(count_per_camera):
                t = t + timedelta(seconds=rnd.randint(8, 300))
                w, h = rnd.choice(SIZES)
                img = _random_scene((w, h), seed=rnd.randint(0, 10 ** 9))

                # 每事件第 1、4 张加横幅文字（仅少量照片含文字）
                if event["banner"] and i in (0, 3):
                    _draw_banner(img, event["banner"])

                # 人像场景画 1-2 张脸；年会随机 0-3 张脸（多人合照）
                face_count = 0
                if "人物" in event["name"] or "年会" in event["name"]:
                    face_count = rnd.randint(1, 3)
                for f in range(face_count):
                    # 人脸直径占画面高度 5%~17%（贴近真实合照比例，便于检测）
                    r = max(140, int(min(h, w) * 0.05)) + rnd.randint(0, int(min(h, w) * 0.06))
                    cx = rnd.randint(r, w - r)
                    cy = rnd.randint(r, h - r)
                    _draw_face(img, cx, cy, r, rnd.randint(0, 10 ** 9))

                exif_bytes = piexif.dump(_make_exif(
                    cam["make"], cam["model"], cam["lens"], t,
                    rnd.choice(ISOS), rnd.choice(APERTURES), rnd.choice(SHUTTERS),
                    w, h,
                ))
                name = f"{cam['prefix']}{4000 + i:04d}.JPG"
                img.save(cam_dir / name, "JPEG", quality=90, exif=exif_bytes)
                total += 1
        print(f"[ok] {event['name']}（{len(event['cameras'])} 台相机）")
    print(f"完成：共生成 {total} 张测试照片 -> {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="生成模拟测试照片集")
    parser.add_argument("--count", type=int, default=40,
                        help="每台相机生成数量（默认 40）")
    parser.add_argument("--out", type=str, default="test_data",
                        help="输出目录（默认 test_data）")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    out = root / args.out
    generate(out, args.count)


if __name__ == "__main__":
    main()
