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
"""Bing 图片搜索通道下载活动照片（HD ≥1080），作为 Commons/wsrv 通路故障时的
主力/补充（2026-10-06：本机代理故障 + commons 被屏蔽 + wsrv 间歇重置，
Bing 是本机唯一稳定检索通道——2026-09-12 已验证）。

输出：test_data_conference/<活动>/b<序号>_<slug>.jpg（b 前缀 = bing 来源）
水印图库域名（alamy/getty 等）过滤；短边 ≥1080 才保留；最长边压到 2560。
仅本地测试用途，不要分发。
"""
import io
import sys
import time
import urllib.parse
from collections import OrderedDict
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_event_photos import bing_image_urls  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "test_data_conference"

# 额外屏蔽水印图库 / 缩略图站 / 中文内容农场（英文查询下混入的无关图）
EXTRA_BLOCK = ("alamy", "shutterstock", "gettyimages", "istockphoto",
               "dreamstime", "123rf", "depositphotos", "agefotostock",
               "imago-images", "picfair", "bigstock", "stockphoto",
               "watermark", "colourbox", "stock.adobe",
               ".cn/", "sciencenet", "ifengimg", "duitang", "itc.cn",
               "sohu", "sinaimg", "163.com", "qq.com", "toutiao",
               "visionexpo", "freepik", "pngtree", "vecteezy", "vatgia", "giagoc", "sendo", "lazada",
               "shopee", "alibaba", "aliexpress", "made-in-china",
               "dhresource", "ecuagenera", "printables", "pinterest")


def looks_like_white_bg(im: Image.Image) -> bool:
    """白底商品图/图表检测：边缘区域大面积接近纯白 → 拒收。
    （Bing 尾部结果混入的电风扇/饮水机/地图等 junk 均为白底图）"""
    small = im.convert("RGB").resize((64, 64))
    px = list(small.getdata())
    border = [p for i, p in enumerate(px)
              if i % 64 in (0, 63) or i // 64 in (0, 63)]
    near_white = sum(1 for r, g, b in border
                     if r > 235 and g > 235 and b > 235)
    return near_white / max(1, len(border)) > 0.85

# (活动目录, 目标张数, [搜索词（多角度：全景/舞台/展位/人群/特写）])
EVENTS = [
    ("01_gamescom_2019", 7, [
        "gamescom 2019 booth crowd hall photo",
        "gamescom 2019 stage show esports",
        "gamescom 2019 visitors cosplay",
    ]),
    ("02_comiccon_2019", 7, [
        "San Diego Comic-Con 2019 panel hall",
        "Comic-Con 2019 cosplay attendees",
        "Comic-Con 2019 exhibit floor crowd",
    ]),
    ("03_wikimania", 3, [
        "Wikimania Katowice conference stage",
        "Wikimania 2024 Katowice attendees",
        "Wikimania conference keynote audience",
        "Wikimania hackathon developers room",
        "Wikimania Stockholm 2019 conference",
        "Wikimania 2023 Singapore session",
    ]),
    ("03b_mwc_barcelona", 5, [
        "Mobile World Congress Barcelona trade show floor",
        "MWC 2019 Barcelona exhibition",
        "Mobile World Congress Fira Barcelona visitors",
        "MWC 2018 Samsung Galaxy booth",
        "Mobile World Congress congress hall speech",
        "Mobile World Congress Barcelona booth hall",
        "MWC Barcelona crowd visitors",
        "Mobile World Congress phone launch stage",
        "Mobile World Congress 2019 Barcelona",
        "MWC Barcelona Samsung LG booth",
    ]),
    ("04_ces_2025", 6, [
        "CES 2025 Las Vegas convention booth",
        "CES Las Vegas exhibition hall crowd",
    ]),
    ("05_oktoberfest_munich", 7, [
        "Oktoberfest Munich beer tent interior crowd",
        "Oktoberfest Wiesn amusement rides carousel",
        "Oktoberfest parade traditional costumes",
        "Oktoberfest Munich beer hall people dirndl",
        "Oktoberfest ferris wheel Munich fair",
        "Oktoberfest Munich Theresienwiese crowd aerial",
        "Oktoberfest pretzel beer stein tent",
        "Oktoberfest Munich tent musicians band",
        "Oktoberfest Wiesn visitors beer garden evening",
        "Oktoberfest Munich tent crowd tables benches",
        "Oktoberfest Munich traditional costume procession horses",
        "Oktoberfest beer Maß people tent Bavaria",
        "Oktoberfest Munich live band brass music tent",
        "Oktoberfest Wiesn 2019 visitors",
    ]),
    ("06_venice_carnival", 7, [
        "Carnival of Venice masks St Mark's Square",
        "Carnevale di Venezia maschere piazza",
        "Venice carnival costume procession",
        "Carnival of Venice mask costume portrait",
        "Venice carnival February crowd canal",
        "Carnevale Venezia 2019 masks",
        "Venice carnival masks gondola",
        "Venice carnival white costume elegant mask",
        "Carnevale di Venezia flight of the angel",
        "Venice carnival San Marco mask costume woman",
        "Venice carnival carnival mask close-up feather headdress",
        "Carnevale Venezia sfilata Piazza San Marco",
    ]),
    ("07_rio_carnival_2011", 5, [
        "Rio Carnival sambadrome parade dancers",
        "Carnival Rio de Janeiro float costume",
        "Rio de Janeiro carnival samba school parade",
        "Brazilian carnival dancers feathers Rio",
        "Rio carnival street bloco crowd",
    ]),
    ("08_rio2016_olympics_100m", 5, [
        "Rio 2016 Olympics 100m final Bolt",
        "Rio 2016 Olympic stadium athletics",
        "Usain Bolt celebrating Rio 2016",
        "Olympic Stadium Rio athletics track crowd",
        "Usain Bolt Rio 2016 gold medal celebration",
        "Rio 2016 Olympics men 100 metres semifinal",
        "Rio 2016 Olympic Games track and field night session",
    ]),
]

# 内容级去重：md5（字节级）+ aHash（像素级，同图不同编码也算重复）
import hashlib  # noqa: E402
import re  # noqa: E402

SEEN_MD5 = set()
SEEN_AHASH = set()


def ahash(im: Image.Image) -> str:
    g = im.convert("L").resize((16, 16))
    px = list(g.getdata())
    avg = sum(px) / len(px)
    return "".join("1" if v > avg else "0" for v in px)


def ahash_dist(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b))


def load_seen(root: Path) -> None:
    for p in root.glob("*/*.jpg"):
        try:
            with Image.open(p) as im:
                SEEN_AHASH.add(ahash(im))
        except Exception:  # noqa: BLE001
            continue


def blocked(url: str) -> bool:
    low = url.lower()
    return any(k in low for k in EXTRA_BLOCK)


def save_hd(url: str, dest: Path) -> bool:
    """下载并校验：短边 ≥1080、md5 不重复才保留；最长边 ≤2560。"""
    import ssl
    import urllib.request
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; "
                          "Win64; x64) Chrome/126.0"})
        data = urllib.request.urlopen(req, timeout=60, context=ctx).read()
        if not (30_000 < len(data) < 40 * 1024 * 1024):
            return False
        m = hashlib.md5(data).hexdigest()
        if m in SEEN_MD5:
            return False
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            w, h = im.size
            if min(w, h) < 1080:
                return False
            im_rgb = im.convert("RGB")
            if looks_like_white_bg(im_rgb):
                return False  # 白底商品图/图表 junk
            hsh = ahash(im_rgb)
            if any(ahash_dist(hsh, s) <= 6 for s in SEEN_AHASH):
                return False  # 像素级重复（同图不同编码）
            im_rgb.thumbnail((2560, 2560), Image.LANCZOS)
            im_rgb.save(dest, "JPEG", quality=90)
        SEEN_MD5.add(m)
        SEEN_AHASH.add(hsh)
        return True
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    OUT.mkdir(exist_ok=True)
    load_seen(OUT)
    total = 0
    rows = []
    for folder, want, queries in EVENTS:
        edir = OUT / folder
        edir.mkdir(parents=True, exist_ok=True)
        have = len([p for p in edir.glob("*.jpg")
                    if not p.name.startswith("_")])
        got = have
        # 修复：从现有最大序号继续编号，避免覆盖已下载文件
        nxt = 0
        for p in edir.glob("b*.jpg"):
            m = re.match(r"b(\d+)", p.name)
            if m:
                nxt = max(nxt, int(m.group(1)))
        print(f"=== {folder} (已有 {have}) ===", flush=True)
        seen_urls = set()
        for q in queries:
            if got >= want:
                break
            for first in (1, 17):  # 两页深挖，避免只拿到首页尾部噪声
                if got >= want:
                    break
                # imagesize:large 让 Bing 只返回大图（多数 ≥1920px）
                us = bing_image_urls(q + " imagesize:large", want=16,
                                     first=first)
                us = [u for u in us
                      if u not in seen_urls and not blocked(u)]
                seen_urls.update(us)
                print(f"  '{q}' p{first} -> {len(us)} 候选", flush=True)
                for u in us:
                    if got >= want:
                        break
                    nxt += 1
                    dest = edir / f"b{nxt:02d}.jpg"
                if save_hd(u, dest):
                    got += 1
                    total += 1
                    rows.append([folder, dest.name, u])
                    print(f"  [ok] {dest.name} <- {u[:90]}", flush=True)
                else:
                    print(f"  [skip] {u[:90]}", flush=True)
                time.sleep(0.8)
        print(f"  {folder}: {got}/{want}", flush=True)

    import csv
    with open(OUT / "bing_sources.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        wtr = csv.writer(f)
        wtr.writerow(["event", "file", "source_url"])
        wtr.writerows(rows)
    print(f"TOTAL_BING={total}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
