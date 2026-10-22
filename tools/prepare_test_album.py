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
"""把零散测试素材整理成"像真实相册"的图集：按事件分组 + 注入 EXIF。

用法:
    python tools/prepare_test_album.py [--out test_album]

产出结构（可直接 pm ingest）:
    test_album/
      00_RAW多品牌素材/        # 复制自 test_data_raw2 的有效 RAW（保留相机原始 EXIF）
      2026-04-12_清华校园参观/  # 以下均为 JPG，注入模拟 EXIF
      2026-07-08_高校走访/
      2026-05-18_美术馆展览/
      2026-06-12_公开课教学/
      2026-09-05_行业论坛/
      library.db              # 由 pm ingest 生成（不在本脚本内）

设计要点：
- 同一事件的照片拍摄时间相邻（间隔数分钟），便于验证**事件时间聚类**
- 不同事件日期拉开，避免被并成同一事件
- 注入相机/镜头/ISO/光圈/快门/GPS，便于验证相机筛选与地图定位
"""
import argparse
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import piexif
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

RAW_EXT = {".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".orf",
           ".rw2", ".raw", ".raf", ".pef", ".ptx", ".dng", ".3fr", ".fff", ".iiq",
           ".rwl", ".mrw", ".mdc", ".mos", ".k25", ".kdc", ".dcr", ".x3f", ".erf",
           ".mef", ".cap", ".dcs", ".drf", ".gpr", ".srw"}

# (事件名, 日期时间, 城市(纬度分,经度分), 相机, 源目录, 文件名匹配前缀)
EVENTS = [
    ("2026-04-12_清华校园参观", datetime(2026, 4, 12, 9, 20),
     ((39, 60), (116, 20)),
     {"make": "SONY", "model": "ILCE-7RM5", "lens": "FE 24-70mm F2.8 GM II", "prefix": "DSC0"},
     "test_data_events/schoolgate", ["schoolgate_0"]),

    ("2026-07-08_高校走访", datetime(2026, 7, 8, 14, 10),
     ((31, 12), (121, 25)),
     {"make": "Canon", "model": "Canon EOS R6 Mark II", "lens": "RF24-105mm F4 L IS USM", "prefix": "_MG_"},
     "test_data_events/schoolgate", ["schoolgate_1", "schoolgate_2"]),

    ("2026-05-18_美术馆展览", datetime(2026, 5, 18, 10, 30),
     ((31, 13), (121, 28)),
     {"make": "FUJIFILM", "model": "X-H2S", "lens": "XF16-55mmF2.8 R LM WR", "prefix": "DSCF"},
     "test_data_events/exhibition", ["exhibition_"]),

    ("2026-06-12_公开课教学", datetime(2026, 6, 12, 8, 50),
     ((23, 8), (113, 16)),
     {"make": "NIKON CORPORATION", "model": "NIKON Z 9", "lens": "NIKKOR Z 24-70mm f/2.8 S", "prefix": "_DSC"},
     "test_data_events/classroom", ["classroom_"]),

    ("2026-09-05_行业论坛", datetime(2026, 9, 5, 15, 0),
     ((22, 32), (114, 3)),
     {"make": "SONY", "model": "ILCE-7RM5", "lens": "FE 70-200mm F2.8 GM II", "prefix": "DSC0"},
     "test_data_events/speech", ["speech_"]),
]

ISOS = [100, 200, 400, 800]
APERTURES = [1.8, 2.8, 4.0, 5.6]
SHUTTERS = [(1, 60), (1, 125), (1, 250), (1, 500)]


def inject_exif(path: Path, cam: dict, dt: datetime, lat, lon, iso, ap, sh):
    zeroth = {
        piexif.ImageIFD.Make: cam["make"].encode("utf-8"),
        piexif.ImageIFD.Model: cam["model"].encode("utf-8"),
        piexif.ImageIFD.Software: b"PhotoManager TestAlbum Injector",
    }
    exif = {
        piexif.ExifIFD.DateTimeOriginal: dt.strftime("%Y:%m:%d %H:%M:%S").encode(),
        piexif.ExifIFD.DateTimeDigitized: dt.strftime("%Y:%m:%d %H:%M:%S").encode(),
        piexif.ExifIFD.LensModel: cam["lens"].encode("utf-8"),
        piexif.ExifIFD.ISOSpeedRatings: iso,
        piexif.ExifIFD.FNumber: (int(ap * 100), 100),
        piexif.ExifIFD.ExposureTime: (sh[1], sh[0]),
        piexif.ExifIFD.FocalLength: (5000, 100),
        piexif.ExifIFD.FocalLengthIn35mmFilm: 50,
    }
    gps = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: lat,
        piexif.GPSIFD.GPSLongitudeRef: b"E",
        piexif.GPSIFD.GPSLongitude: lon,
    }
    piexif.insert(piexif.dump({"0th": zeroth, "Exif": exif, "GPS": gps}), str(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="test_album")
    args = ap.parse_args()

    out = ROOT / args.out
    if out.exists():
        print(f"[!] 输出目录已存在: {out}（已存在的文件会跳过）")
    out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(20260912)

    total = 0
    # 1) 复制有效 RAW（保留相机原始 EXIF）
    raw_src = ROOT / "test_data_raw2"
    raw_dst = out / "00_RAW多品牌素材"
    if raw_src.exists():
        raw_dst.mkdir(parents=True, exist_ok=True)
        n = 0
        for p in sorted(raw_src.iterdir()):
            if p.is_file() and p.suffix.lower() in RAW_EXT and p.stat().st_size > 1000:
                t = raw_dst / p.name
                if not t.exists():
                    shutil.copy2(p, t)
                    n += 1
        print(f"[RAW] 复制 {n} 个 -> {raw_dst.name}")
        total += n

    # 2) 事件分组 + EXIF 注入
    for name, dt, city, cam, src_rel, prefixes in EVENTS:
        src = ROOT / src_rel
        if not src.exists():
            print(f"[skip] 源目录不存在: {src}")
            continue
        files = []
        for pre in prefixes:
            files += sorted(src.glob(f"{pre}*.jpg"))
        files = [f for f in files if f.name != "_sheet.jpg"]
        if not files:
            print(f"[skip] {name}: 无匹配文件")
            continue
        ev_dir = out / name
        ev_dir.mkdir(parents=True, exist_ok=True)
        t = dt
        for i, f in enumerate(files, 1):
            target = ev_dir / f"{cam['prefix']}{i:04d}.JPG"
            if not target.exists():
                img = Image.open(f).convert("RGB")
                img.save(target, "JPEG", quality=92)
                lat = ((city[0][0], 1), (city[0][1], 1), (rnd.randint(0, 59), 1))
                lon = ((city[1][0], 1), (city[1][1], 1), (rnd.randint(0, 59), 1))
                inject_exif(target, cam, t, lat, lon,
                            rnd.choice(ISOS), rnd.choice(APERTURES), rnd.choice(SHUTTERS))
            t += timedelta(minutes=rnd.randint(4, 15))
        print(f"[ok] {name}: {len(files)} 张")
        total += len(files)

    print(f"\n完成，共 {total} 个文件 -> {out}")
    print("下一步：")
    print(f"  .venv\\Scripts\\python.exe -m photo_manager.cli --db {args.out}\\library.db ingest {args.out}")


if __name__ == "__main__":
    main()
