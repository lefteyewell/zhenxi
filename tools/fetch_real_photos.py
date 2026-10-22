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
"""真实照片下载 + EXIF 注入工具。

从 Unsplash CDN（images.unsplash.com，国内可直连）下载真实照片，
并写入相机 / 镜头 / 拍摄时间 / GPS / 曝光参数等 EXIF 元数据，
形成可完整测试 EXIF 读取、事件聚类、GPS 定位、缩略图、人脸、OCR 的真实图集。

设计：
- 覆盖 人脸 / 文字 / 风景 / 城市 / 动物 / 建筑 / 美食 / 海滩 / 花卉 / 汽车 / 科技 等类别
- 按"事件"分文件夹（模拟多场活动、多相机），相邻拍摄时间便于事件聚类
- 下载失败自动重试 2 次；跳过无法下载的图片
- 可重复运行（幂等，已存在文件跳过）

用法:
    python tools/fetch_real_photos.py [--out test_data_real] [--size 1200] [--limit N]
"""
import argparse
import io
import random
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import piexif
from PIL import Image

# ---------------------------------------------------------------------------
# 图集定义：事件 -> 相机 -> 照片（Unsplash photo id + 名称）
# ---------------------------------------------------------------------------

# (unsplash photo id, 中文描述, 类别)
PHOTOS = {
    "face": [
        ("1507003211169-0a1dd7228f2d", "男士肖像", "人脸"),
        ("1494790108377-be9c29b29330", "女士肖像", "人脸"),
        ("1500648767791-00dcc994a43e", "男士头像特写", "人脸"),
        ("1438761681033-6461ffad8d80", "女士头像", "人脸"),
        ("1508214751196-bcfd4ca60f91", "女士侧脸", "人脸"),
        ("1544005313-94ddf0286df2", "女士正脸", "人脸"),
        ("1506794778202-cad84cf45f1d", "男士正脸", "人脸"),
        ("1531123897727-8f129e1688ce", "女士微笑", "人脸"),
    ],
    "text": [
        ("1481487196290-c152efe083f5", "代码屏幕", "文字"),
        ("1461749280684-dccba630e2f6", "编辑器界面", "文字"),
        ("1515879218367-8466d910aaa4", "代码高亮", "文字"),
        ("1497366216548-37526070297c", "办公文件", "文字"),
        ("1455390582262-044cdead277a", "书写笔记", "文字"),
    ],
    "landscape": [
        ("1506905925346-21bda4d32df4", "雪山", "风景"),
        ("1501785888041-af3ef285b470", "湖畔", "风景"),
        ("1470071459604-3b5ec3a7fe05", "晨雾山谷", "风景"),
        ("1469474968028-56623f02e42e", "日出山野", "风景"),
        ("1441974231531-c6227db76b6e", "森林阳光", "风景"),
    ],
    "city": [
        ("1477959858617-67f85cf4f1df", "城市天际线", "城市"),
        ("1449824913935-59a10b8d2000", "城市街道", "城市"),
        ("1444723121867-7a241cacace9", "高楼建筑群", "城市"),
        ("1519501025264-65ba15a82390", "城市夜景", "城市"),
        ("1480714378408-67cf0d13bc1b", "都市交通", "城市"),
    ],
    "animal": [
        ("1548199973-03cce0bbc87b", "两只狗", "动物"),
        ("1450778869180-41d0601e046e", "猫", "动物"),
        ("1425082661705-1834bfd09dca", "仓鼠", "动物"),
    ],
    "other": [
        ("1487958449943-2429e8be8625", "白色建筑", "建筑"),
        ("1504674900247-0877df9cc836", "美食摆盘", "美食"),
        ("1512621776951-a57141f2eefd", "沙拉", "美食"),
        ("1507525428034-b723cf961d3e", "海滩", "海滩"),
        ("1490750967868-88aa4486c946", "花卉", "花卉"),
        ("1502877338535-766e1452684a", "跑车", "汽车"),
        ("1518770660439-4636190af475", "芯片特写", "科技"),
    ],
    "technology": [
        ("1518770660439-4636190af475", "芯片特写", "科技"),
    ],
    "beach": [
        ("1507525428034-b723cf961d3e", "海滩", "海滩"),
    ],
    "flower": [
        ("1490750967868-88aa4486c946", "花卉", "花卉"),
    ],
    "food": [
        ("1504674900247-0877df9cc836", "美食摆盘", "美食"),
        ("1512621776951-a57141f2eefd", "沙拉", "美食"),
    ],
    "sport": [
        ("1461896836934-ffe607ba8211", "田径跑道", "运动"),
        ("1530549387789-4c1017266635", "健身举重", "运动"),
    ],
    "music": [
        ("1511671782779-c97d3d27a1d4", "弹钢琴", "音乐"),
        ("1508700115892-45ecd05ae2ad", "耳机音乐", "音乐"),
    ],
    "space": [
        ("1419242902214-272b3f66ee7a", "星空银河", "天文"),
    ],
    "travel": [
        ("1488646953014-85cb44e25828", "旅行背包", "旅行"),
        ("1503220317375-aaad61436b1b", "海边旅行", "旅行"),
        ("1469854523086-cc02fe5d8800", "旅行地图", "旅行"),
    ],
    "coffee": [
        ("1447933601403-0c6688de566e", "咖啡拉花", "咖啡"),
        ("1509042239860-f550ce710b93", "咖啡豆", "咖啡"),
    ],
    "interior": [
        ("1522708323590-d24dbb6b0267", "客厅", "室内"),
        ("1513694203232-719a280e022f", "室内", "室内"),
    ],
    "wedding": [
        ("1519741497674-611481863552", "婚礼", "婚礼"),
        ("1465495976277-4387d4b0b4c6", "婚礼花", "婚礼"),
    ],
    "plant": [
        ("1545241047-6083a3684587", "盆栽植物", "植物"),
    ],
    "water": [
        ("1439405326854-014607f694d7", "海洋", "海洋"),
        ("1505142468610-359e7d316be0", "海浪", "海洋"),
    ],
    "library": [
        ("1521587760476-6c12a4b040da", "图书馆", "摄影"),
        ("1507842217343-583bb7270b66", "书架", "摄影"),
    ],
    "market": [
        ("1488459716781-31db52582fe9", "菜市场", "集市"),
    ],
    "transport": [
        ("1500964757637-c85e8a162699", "火车", "交通"),
        ("1436491865332-7a61a109cc05", "飞机", "交通"),
        ("1449965408869-eaa3f722e40d", "海边小船", "交通"),
    ],
    "snow": [
        ("1483664852095-d6cc6870702d", "雪山冬景", "雪景"),
    ],
    "night": [
        ("1502134249126-9f3755a50d78", "城市夜晚", "夜景"),
        ("1476673160081-cf065607f449", "霓虹夜景", "夜景"),
    ],
}

# 每个事件（文件夹）的照片组成：事件名 -> [(类别, 张数)]
EVENTS = [
    {
        "name": "2025-04-20_产品发布与街拍",
        "date": datetime(2025, 4, 20, 10, 0),
        "slots": [
            ("text", 2), ("city", 2), ("technology", 1), ("face", 1),
        ],
        "cameras": [
            {"make": "SONY", "model": "ILCE-7RM5", "lens": "FE 24-70mm F2.8 GM II", "folder": "sony_a7rm5", "prefix": "DSC0"},
            {"make": "Canon", "model": "Canon EOS R6 Mark II", "lens": "RF70-200mm F2.8 L IS USM", "folder": "canon_r6m2", "prefix": "_MG_"},
        ],
    },
    {
        "name": "2025-06-30_户外风景与动物",
        "date": datetime(2025, 6, 30, 6, 45),
        "slots": [
            ("landscape", 3), ("animal", 2), ("beach", 1),
        ],
        "cameras": [
            {"make": "Canon", "model": "Canon EOS R6 Mark II", "lens": "RF15-35mm F2.8 L IS USM", "folder": "canon_r6m2", "prefix": "_MG_"},
            {"make": "NIKON CORPORATION", "model": "NIKON Z 9", "lens": "NIKKOR Z 70-200mm f/2.8 VR S", "folder": "nikon_z9", "prefix": "_DSC"},
        ],
    },
    {
        "name": "2025-08-15_人物写真与生活",
        "date": datetime(2025, 8, 15, 16, 30),
        "slots": [
            ("face", 5), ("food", 2), ("flower", 1),
        ],
        "cameras": [
            {"make": "SONY", "model": "ILCE-7RM5", "lens": "FE 85mm F1.4 GM", "folder": "sony_a7rm5", "prefix": "DSC0"},
            {"make": "FUJIFILM", "model": "X-H2S", "lens": "XF16-55mmF2.8 R LM WR", "folder": "fuji_xh2s", "prefix": "DSCF"},
        ],
    },
    {
        "name": "2025-10-05_城市与建筑",
        "date": datetime(2025, 10, 5, 9, 15),
        "slots": [
            ("city", 2), ("other", 1), ("animal", 1), ("text", 1),
        ],
        "cameras": [
            {"make": "Canon", "model": "Canon EOS R6 Mark II", "lens": "RF24-105mm F4 L IS USM", "folder": "canon_r6m2", "prefix": "_MG_"},
            {"make": "SONY", "model": "ILCE-7RM5", "lens": "FE 16-35mm F2.8 GM", "folder": "sony_a7rm5", "prefix": "DSC0"},
        ],
    },
    {
        "name": "2025-12-28_旅行与休闲光影",
        "date": datetime(2025, 12, 28, 10, 30),
        "slots": [
            ("travel", 2), ("coffee", 1), ("interior", 1), ("music", 1),
            ("library", 1), ("market", 1), ("sport", 1), ("transport", 1),
            ("snow", 1),
        ],
        "cameras": [
            {"make": "FUJIFILM", "model": "X-H2S", "lens": "XF16-55mmF2.8 R LM WR", "folder": "fuji_xh2s", "prefix": "DSCF"},
            {"make": "SONY", "model": "ILCE-7RM5", "lens": "FE 24-70mm F2.8 GM II", "folder": "sony_a7rm5", "prefix": "DSC0"},
        ],
    },
]

SIZES = [(1200, 800), (1200, 675), (800, 1200), (1200, 1200)]
ISOS = [100, 200, 400, 800]
APERTURES = [1.8, 2.8, 4.0, 5.6]
SHUTTERS = [(1, 60), (1, 125), (1, 250), (1, 500)]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 北京/上海/广州/深圳/成都 代表坐标
CITIES = [
    ((39, 54), (116, 23), "北京"),
    ((31, 14), (121, 29), "上海"),
    ((23, 7), (113, 15), "广州"),
    ((22, 33), (114, 4), "深圳"),
    ((30, 34), (104, 4), "成都"),
]


def _download(url: str, retries: int = 2) -> bytes:
    last = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            return urllib.request.urlopen(req, timeout=40).read()
        except Exception as e:
            last = e
            time.sleep(1.5)
    raise last


def _inject_exif(img_path: Path, cam: dict, dt: datetime,
                 lat_dms, lon_dms, lat_ref, lon_ref, w: int, h: int,
                 iso, aperture, shutter):
    """写入完整 EXIF：相机/镜头/时间/GPS/曝光/尺寸。"""
    zeroth = {
        piexif.ImageIFD.Make: cam["make"].encode("utf-8"),
        piexif.ImageIFD.Model: cam["model"].encode("utf-8"),
        piexif.ImageIFD.Software: "PhotoManager Real-Photo Injector".encode("utf-8"),
        piexif.ImageIFD.Artist: "Unsplash Photographer".encode("utf-8"),
    }
    exif = {
        piexif.ExifIFD.DateTimeOriginal: dt.strftime("%Y:%m:%d %H:%M:%S").encode(),
        piexif.ExifIFD.DateTimeDigitized: dt.strftime("%Y:%m:%d %H:%M:%S").encode(),
        piexif.ExifIFD.LensModel: cam["lens"].encode("utf-8"),
        piexif.ExifIFD.ISOSpeedRatings: iso,
        piexif.ExifIFD.FNumber: (int(aperture * 100), 100),
        piexif.ExifIFD.ExposureTime: (shutter[1], shutter[0]),
        piexif.ExifIFD.FocalLength: (5000, 100),
        piexif.ExifIFD.FocalLengthIn35mmFilm: 50,
        piexif.ExifIFD.ExifVersion: b"0231",
    }
    gps = {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: lat_dms,
        piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        piexif.GPSIFD.GPSLongitude: lon_dms,
    }
    first = {
        piexif.ImageIFD.XResolution: (300, 1),
        piexif.ImageIFD.YResolution: (300, 1),
    }
    piexif.insert(piexif.dump({"0th": zeroth, "Exif": exif, "GPS": gps, "1st": first}),
                  str(img_path))


def fetch(out_dir: Path, size: int = 1200, limit: int = None) -> dict:
    out_dir = Path(out_dir)
    rnd = random.Random(20260806)
    stats = {"downloaded": 0, "skipped": 0, "failed": 0}

    for ev in EVENTS:
        cam_pool = list(ev["cameras"])
        cam_seq = {cam["folder"]: 0 for cam in cam_pool}  # 相机文件序号
        t = ev["date"]
        ev_dir = out_dir / ev["name"]
        for cat, n in ev["slots"]:
            cam = cam_pool[rnd.randrange(len(cam_pool))]
            photos = PHOTOS[cat]
            used = []
            for i in range(n):
                if limit and stats["downloaded"] >= limit:
                    return stats
                pid, desc, cat_label = photos[rnd.randrange(len(photos))]
                if pid in used:
                    continue
                used.append(pid)
                cam_dir = ev_dir / cam["folder"]
                cam_dir.mkdir(parents=True, exist_ok=True)
                seq = cam_seq[cam["folder"]]
                cam_seq[cam["folder"]] += 1
                name = f"{cam['prefix']}{seq + 4000:04d}.JPG"
                target = cam_dir / name
                if target.exists():
                    stats["skipped"] += 1
                    continue
                url = f"https://images.unsplash.com/photo-{pid}?w={size}&q=80"
                try:
                    data = _download(url)
                    img = Image.open(io.BytesIO(data))
                    img = img.convert("RGB")
                    if img.width < 600:
                        img = img.resize((size, int(size * img.height / img.width)))
                    img.thumbnail((size, size), Image.LANCZOS)
                    img = img.convert("RGB")
                    t = t + timedelta(seconds=rnd.randint(60, 900))
                    lat_d, lon_d = CITIES[rnd.randrange(len(CITIES))][:2]
                    lat_ref = b"N" if lat_d[0] >= 0 else b"S"
                    lon_ref = b"E" if lon_d[0] >= 0 else b"W"
                    lat_dms = ((abs(lat_d[0]), 1), (lat_d[1], 1), (rnd.randint(0, 59), 1))
                    lon_dms = ((abs(lon_d[0]), 1), (lon_d[1], 1), (rnd.randint(0, 59), 1))
                    img.save(target, "JPEG", quality=90)
                    _inject_exif(target, cam, t, lat_dms, lon_dms, lat_ref, lon_ref,
                                 img.width, img.height,
                                 rnd.choice(ISOS), rnd.choice(APERTURES),
                                 rnd.choice(SHUTTERS))
                    stats["downloaded"] += 1
                    print(f"[ok] {ev['name']}/{cam['folder']}/{name}  "
                          f"{cat_label}·{desc}  {img.width}x{img.height}")
                except Exception as e:
                    stats["failed"] += 1
                    print(f"[x]  {pid} {desc}: {type(e).__name__} {e}")
        print(f"--- {ev['name']} 完成（下载 {stats['downloaded']} / 跳过 {stats['skipped']} / 失败 {stats['failed']}）")
    return stats


def main():
    parser = argparse.ArgumentParser(description="下载真实照片并注入 EXIF")
    parser.add_argument("--out", default="test_data_real",
                        help="输出目录（默认 test_data_real）")
    parser.add_argument("--size", type=int, default=1200, help="长边尺寸（默认 1200）")
    parser.add_argument("--limit", type=int, default=None, help="最多下载张数")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    stats = fetch(root / args.out, size=args.size, limit=args.limit)
    print(f"完成：下载 {stats['downloaded']} / 跳过 {stats['skipped']} / 失败 {stats['failed']}")


if __name__ == "__main__":
    main()
