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
"""抓取"活动场景"测试照片：新闻发布会 / 展览会 / 上课 / 演讲。

背景（2026-09-12）：常规免费图库的程序化抓取在本机网络下基本不可用——
Unsplash 搜索被 Anubis 反爬拦截(401)、Pexels/Pixabay/StockSnap 返回 403、
Wikimedia/Openverse 走代理是 502。可直连的只有 Unsplash CDN（需已知 photo id，
无法按主题检索）。Bing 图片搜索是当前唯一能按主题获得真实照片直链的通道，
因此本脚本走 Bing，并对结果做域名黑名单过滤 + 人工/视觉复核。

注意：Bing 结果版权来源混杂，仅用于本地功能测试，不要分发或商用。

用法:
    python tools/fetch_event_photos.py --out test_data_events --per-topic 10
"""
import argparse
import html as ihtml
import io
import re
import ssl
import time
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")}

# 主题 -> （中英文搜索词，轮流尝试以提高命中）
# 搜索词是调出来的（2026-09-12 实测教训）：
#   - "新闻发布会 现场 主席台 话筒" 会命中广电素材服务器的**电视节目截图**，不是发布会
#   - "大学课堂 上课 学生 教室" 会命中高校官网的**宿舍文化墙/手抄报**
#   - 英文词会被 japan-guide 等旅游博客占坑（keynote speaker -> 大阪观光图）
# 因此优先用"现场/实拍"类中文词 + 具体物件词。
TOPICS = OrderedDict([
    ("press", ["产品发布会 现场照片 大屏幕 观众",
               "press conference room"]),
    ("exhibition", ["exhibition hall booth trade show visitors",
                    "展览会 展位 现场 观众"]),
    ("classroom", ["老师 授课 现场 教室 照片",
                   "teacher lecturing students classroom blackboard photo"]),
    ("speech", ["报告厅 演讲 现场照片 听众",
                "speaker giving talk seminar audience photo"]),
    # 校门照：牌匾上通常有校名题字，是很实用的 OCR 测试素材
    # 分词坑（实测）：搜"武汉大学"会被切成"武汉+大学"，返回黄鹤楼/长江大桥等武汉景点；
    # 带"中国"会命中中国地图。要用"清华校门"这类连写简称，或第一轮成功的"大学校门 校名"。
    ("schoolgate", ["清华校门 复旦校门 浙大校门 交大校门",
                    "大学校门 实拍 大门"]),
])

# 素材站 / logo / 文档类站点：出来的多是设计素材或图标，不是真实现场照
BLOCK_HOST = ("588ku", "51wendang", "archina", "yayasan", "2008php",
              "cxyclub", "grandocean", "png", "icon", "logo", "vector",
              "quanjing", "tukuchina", "nipic", "zhimg.com/v2", "bpic.")


def _get(url: str, timeout: int = 45, binary: bool = True):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout, context=ctx).read()


def bing_image_urls(query: str, want: int = 20, first: int = 1) -> list:
    url = ("https://www.bing.com/images/search?q="
           + urllib.parse.quote(query)
           + f"&form=HDRSC2&first={first}&mkt=en-US&setlang=en-US")
    try:
        h = _get(url).decode("utf-8", "ignore")
    except Exception as e:
        print(f"    [search-fail] {query}: {type(e).__name__}")
        return []
    blocks = re.findall(r'class="iusc"[^>]*m="([^"]+)"', h)
    out = []
    for b in blocks:
        s = ihtml.unescape(b)
        m = re.search(r'"murl":"(.*?)"', s)
        if not m:
            continue
        u = m.group(1)
        if not re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", u, re.I):
            continue
        if any(k in u.lower() for k in BLOCK_HOST):
            continue
        out.append(u)
    return list(OrderedDict.fromkeys(out))[:want]


def download(url: str, dest: Path, max_mb: float = 12.0) -> bool:
    try:
        data = _get(url, timeout=60)
        if len(data) > max_mb * 1024 * 1024 or len(data) < 8000:
            return False
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        if img.width < 500 or img.height < 350:
            return False
        img.thumbnail((1600, 1600), Image.LANCZOS)
        img.save(dest, "JPEG", quality=88)
        return True
    except Exception:
        return False


def make_sheet(files, out_path, cols=4, cell=300):
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)
    except Exception:
        font = ImageFont.load_default()
    thumbs = []
    for p in files:
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((cell - 8, cell - 8), Image.LANCZOS)
            thumbs.append((p.name, im))
        except Exception:
            continue
    if not thumbs:
        return None
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 22)), (245, 245, 245))
    dr = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(thumbs):
        r, c = divmod(i, cols)
        x, y = c * cell, r * (cell + 22)
        sheet.paste(im, (x + (cell - im.width) // 2, y + 22 + (cell - 8 - im.height) // 2))
        dr.text((x + 4, y + 4), f"{i:02d} {name[:26]}", fill=(0, 0, 0), font=font)
    sheet.save(out_path, "JPEG", quality=88)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="test_data_events")
    ap.add_argument("--per-topic", type=int, default=10)
    ap.add_argument("--only", default=None,
                    help="只抓指定主题，逗号分隔（press,exhibition,classroom,speech）")
    args = ap.parse_args()

    out_root = ROOT / args.out
    out_root.mkdir(parents=True, exist_ok=True)

    topics = TOPICS
    if args.only:
        want = [t.strip() for t in args.only.split(",") if t.strip()]
        topics = OrderedDict((k, v) for k, v in TOPICS.items() if k in want)

    for topic, queries in topics.items():
        tdir = out_root / topic
        tdir.mkdir(parents=True, exist_ok=True)
        print(f"=== {topic} ===")
        cands = []
        for q in queries:
            us = bing_image_urls(q, want=args.per_topic + 6)
            print(f"  '{q}' -> {len(us)} 候选")
            cands += us
            time.sleep(1.0)
        cands = list(OrderedDict.fromkeys(cands))
        ok = 0
        for i, u in enumerate(cands):
            if ok >= args.per_topic:
                break
            dest = tdir / f"{topic}_{ok+1:02d}.jpg"
            if download(u, dest):
                ok += 1
                print(f"  [ok] {dest.name}  <- {u[:80]}")
        sheet = make_sheet([p for p in sorted(tdir.glob("*.jpg"))
                            if p.name != "_sheet.jpg"], tdir / "_sheet.jpg")
        print(f"  下载 {ok} 张，联系表: {sheet}")


if __name__ == "__main__":
    main()
