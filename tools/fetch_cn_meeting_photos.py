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
"""Bing 图片搜索通道下载"中国大陆国家机关/国企/大企业各类会议"测试照片。

用途：本地照片管理软件功能测试数据（导入/缩略图/人脸/OCR/语义检索等）。
HD ≥1080；最长边压到 2560；md5 + 感知哈希（aHash 汉明距≤6）双重去重；
白底商品图/图表 junk 检测；水印图库/素材站域名过滤。

与 fetch_bing_event_photos.py 的区别：
  - 检索市场改为 mkt=zh-CN（中文会议照片多在中文站点）
  - 不再屏蔽中文新闻域名（.cn/sohu/163/qq 等），因为它们正是本批来源
  - 仅屏蔽带水印的图库（alamy/getty/全景/视觉中国等）与设计素材站
  - 查询词为中文"会议现场"类，覆盖国家机关/国企/大企业多种会议类型

仅本地测试用途，不要分发。每张来源见 sources.csv。
"""
import hashlib
import html as ihtml
import io
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "test_data_cn_meetings"

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")}

# 带水印的图库 / 设计素材站（出来的多为带标素材图，不是真实会议现场照）
STOCK_HOST = ("alamy", "shutterstock", "gettyimages", "istockphoto", "dreamstime",
              "123rf", "depositphotos", "agefotostock", "bigstock", "stock.adobe",
              "picfair", "colourbox", "panophotography", "quanjing", "tukuchina",
              "nipic", "588ku", "51wendang", "cfp", "visualchina", "chinafotopress",
              " imaginechina", "imaginchina", "cnsphoto", "pngtree", "vecteezy",
              "freepik", "fotosearch", "silukr", "megapixl", "pixta", "peopleimages",
              "adobestock", "storyblocks", "vectorstock", "canstockphoto", "wireimage",
              "barcroftmedia", "zumapress", "eastnews", "rexfeatures", "xdyanbao",
              "699pic", "shetu66", "tukuppt", "tukuchina", "duitang", "adwest",
              "777ppt", "aigei", "3dmgame", "smzdm", "zhihu", "zhihainiao", "baofun",
              "chuimg", "51img2", "51txapp", "ztupic", "qiantucdn", "dtstatic",
              "nximg", "pica.zhimg", "pic4.zhimg", "pic3.zhimg", "pic1.zhimg",
              "c-ssl.duitang", "am.zdmimg")


def bing_image_urls(query: str, want: int = 20, first: int = 1) -> list:
    url = ("https://www.bing.com/images/search?q="
           + urllib.parse.quote(query)
           + f"&form=HDRSC2&first={first}&mkt=zh-CN&setlang=zh-CN")
    try:
        req = urllib.request.Request(url, headers=UA)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        h = urllib.request.urlopen(req, timeout=45, context=ctx).read().decode(
            "utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
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
        if any(k in u.lower() for k in STOCK_HOST):
            continue
        out.append(u)
    return list(OrderedDict.fromkeys(out))[:want]


def looks_like_white_bg(im: Image.Image) -> bool:
    """白底商品图/图表检测：边缘区域大面积接近纯白 → 拒收。"""
    small = im.convert("RGB").resize((64, 64))
    px = list(small.getdata())
    border = [p for i, p in enumerate(px)
              if i % 64 in (0, 63) or i // 64 in (0, 63)]
    near_white = sum(1 for r, g, b in border
                     if r > 235 and g > 235 and b > 235)
    return near_white / max(1, len(border)) > 0.85


def ahash(im: Image.Image) -> str:
    g = im.convert("L").resize((16, 16))
    px = list(g.getdata())
    avg = sum(px) / len(px)
    return "".join("1" if v > avg else "0" for v in px)


def ahash_dist(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b))


SEEN_MD5 = set()
SEEN_AHASH = set()


def load_seen(root: Path) -> None:
    for p in root.glob("*/*.jpg"):
        try:
            with Image.open(p) as im:
                SEEN_AHASH.add(ahash(im))
        except Exception:  # noqa: BLE001
            continue


def save_hd(url: str, dest: Path) -> bool:
    """下载并校验：短边 ≥1080、md5 不重复才保留；最长边 ≤2560。"""
    import urllib.request as ur
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = ur.Request(url, headers=UA)
        data = ur.urlopen(req, timeout=60, context=ctx).read()
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
                return False
            hsh = ahash(im_rgb)
            if any(ahash_dist(hsh, s) <= 6 for s in SEEN_AHASH):
                return False
            im_rgb.thumbnail((2560, 2560), Image.LANCZOS)
            im_rgb.save(dest, "JPEG", quality=90)
        SEEN_MD5.add(m)
        SEEN_AHASH.add(hsh)
        return True
    except Exception:  # noqa: BLE001
        return False


# (活动目录, 目标张数, [搜索词——多角度：全景/主席台/代表席/发言人/特写])
EVENTS = [
    ("01_lianghui_npc_cppcc", 5, [
        "全国两会 人民大会堂 会议现场 代表",
        "全国人民代表大会 全体会议 人民大会堂",
        "全国政协 会议 主席台 委员",
        "两会 记者会 现场 发言人",
    ]),
    ("02_state_council", 5, [
        "国务院常务会议 现场 会议室",
        "国务院 工作会议 领导 出席",
        "国务院全体会议 现场",
    ]),
    ("03_politburo", 5, [
        "中共中央政治局会议 现场 新华社",
        "中央全会 会场 出席",
        "党和国家 重要会议 现场",
        "中央政治局 会议 大会堂",
    ]),
    ("04_gov_press_conference", 5, [
        "国新办 新闻发布会 现场 发言人",
        "部委 新闻发布会 记者 提问",
        "国务院新闻办 发布会 现场",
        "记者招待会 现场 实拍 部长",
    ]),
    ("05_supreme_court_procuratorate", 5, [
        "最高人民法院 工作会议 现场",
        "最高人民检察院 会议 检察长",
        "全国法院 工作会议 会场",
    ]),
    ("06_central_soe_meeting", 5, [
        "中央企业 年度工作会议 现场",
        "国家电网 工作会议 会场",
        "中石油 工作会议 出席",
        "国资央企 会议 现场",
    ]),
    ("07_soe_labor_congress", 5, [
        "国有企业 职工代表大会 现场",
        "职代会 职工代表 投票 会场",
        "国企 表彰大会 颁奖 现场",
    ]),
    ("08_huawei_launch", 5, [
        "华为 发布会 现场 舞台",
        "华为 合作伙伴大会 会场",
        "华为 新品发布会 观众 演讲",
    ]),
    ("09_corp_annual_meeting", 5, [
        "企业 年会 现场 舞台 员工",
        "互联网公司 年会 颁奖 表演",
        "上市公司 年会 会场 领导",
        "公司 年终庆典 大合照 舞台",
    ]),
    ("10_corp_shareholders_forum", 5, [
        "上市公司 股东大会 现场 股东 投票",
        "董事会 现场 董事 会议桌 出席",
        "企业家 论坛 演讲 嘉宾 现场",
        "业绩说明会 投资者 交流会 现场",
    ]),
]


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
            for first in (1, 17, 33):  # 三页深挖，避免只拿到首页尾部噪声
                if got >= want:
                    break
                us = bing_image_urls(q + " imagesize:large", want=16, first=first)
                us = [u for u in us
                      if u not in seen_urls and not any(
                          k in u.lower() for k in STOCK_HOST)]
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
    csv_path = OUT / "sources.csv"
    new_csv = not csv_path.exists()
    with open(csv_path, "a", newline="",
              encoding="utf-8-sig") as f:
        wtr = csv.writer(f)
        if new_csv:
            wtr.writerow(["event", "file", "source_url"])
        wtr.writerows(rows)
    print(f"TOTAL={total}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
