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
"""从 raw.pixls.us 抓取 RAW 样本清单 / 下载样本。

raw.pixls.us 是 CC0 授权的相机 RAW 样本库。
数据源：https://raw.pixls.us/json/getrepository.php?set=all （DataTables Ajax，共 2000+ 样本）

重要限制（已于 2026-09-12 核实）：
  该站出于法律原因**明确不收人物照片**（"Photographs of people, for legal reasons"），
  偏好"well-lit, pattern-full, scenery"。因此**同一人物多张**的素材基本无法从此源获得，
  需另找源（如 Signature Edits / DPReview 人像样张 / Wesaturate）。
  街景与建筑样本中可能含招牌、横幅等文字，可用于 OCR 测试——需下载后人工/视觉筛图确认。

用法:
    python tools/fetch_raw_samples.py --list --limit 30         # 列清单
    python tools/fetch_raw_samples.py --list --brand Sony       # 按品牌列
    python tools/fetch_raw_samples.py --download --spread --per-brand 2 --limit 20
    python tools/fetch_raw_samples.py --download --brand Canon --limit 5
"""
import argparse
import json
import re
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

JSON_URL = "https://raw.pixls.us/json/getrepository.php?set=all"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
ROOT = Path(__file__).resolve().parent.parent

# 常见 RAW 扩展名
RAW_EXT = {".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".orf",
           ".rw2", ".raw", ".raf", ".pef", ".ptx", ".dng", ".3fr", ".fff", ".iiq",
           ".rwl", ".mrw", ".mdc", ".mos", ".k25", ".kdc", ".dcr", ".x3f", ".erf",
           ".mef", ".cap", ".dcs", ".dcr", ".drf", ".gpr", ".srw", ".tif"}


def _norm_url(url: str) -> str:
    """对 URL 路径做百分号编码。

    样本文件名常含空格/括号（如 "Canon - EOS 7D - RAW (3:2).CR2"），
    直接交给 urllib 会报 "URL can't contain control characters"（2026-09-12 踩过）。
    """
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, urllib.parse.quote(parts.path),
         parts.query, parts.fragment))


def _get(url: str, timeout: int = 90) -> bytes:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout, context=ctx).read()


def _extract_link(html: str):
    m = re.search(r"href='([^']+)'", html) or re.search(r'href="([^"]+)"', html)
    return m.group(1) if m else None


def _safe_name(name: str) -> str:
    """转成 Windows 合法文件名。

    坑（2026-09-12）：样本名常含 "(3:2)"、"(16:9)" 这类画幅标记，**冒号在 Windows
    会被 NTFS 当作备用数据流(ADS)分隔符**，文件名被静默截断成 "xxx (3"，扩展名丢失，
    后续按扩展名查找 RAW 就会漏掉绝大部分文件。此处把非法字符统一换成 "-"。
    """
    bad = '<>:"/\\|?*'
    out = "".join("-" if c in bad else c for c in name)
    out = re.sub(r"\s+", " ", out).strip().rstrip(".")
    return out or "sample.raw"


def _extract_size(html: str) -> float:
    m = re.search(r"\(([\d.]+)MB\)", html)
    return float(m.group(1)) if m else 0.0


def _extract_name(url: str, link_html: str = "") -> str:
    """优先从下载 URL 末尾取文件名（最可靠），失败时退回 <a> 文本。

    注意：不能靠 "sha256" 切分去标签后的文本——title/sha256 字样属于标签内部，
    去标签时会被一起移除，导致文件名解析错误（2026-09-12 踩过）。
    """
    tail = url.rsplit("/", 1)[-1]
    name = urllib.parse.unquote(tail)
    if Path(name).suffix:
        return name
    m = re.search(r">([^<]+)</a>", link_html)
    if m:
        return m.group(1).strip()
    return name


def fetch_all() -> list:
    """返回 [{'brand','model','desc','name','url','size_mb'}]"""
    d = json.loads(_get(JSON_URL).decode("utf-8", "ignore"))
    rows = d["data"] if isinstance(d, dict) and "data" in d else d
    out = []
    for r in rows:
        if len(r) < 8:
            continue
        brand, model, desc = r[0], r[1], r[2]
        link_html = r[7]
        url = _extract_link(link_html)
        if not url:
            continue
        name = _extract_name(url, link_html)
        ext = Path(name).suffix.lower()
        if ext not in RAW_EXT:
            continue
        out.append({"brand": brand, "model": model, "desc": desc,
                    "name": name, "url": url, "size_mb": _extract_size(link_html)})
    return out


def pick_spread(items: list, per_brand: int, limit: int,
                max_mb: float = 40.0) -> list:
    """按品牌分散挑选，每个品牌最多 per_brand 个，排除过大的文件。"""
    by_brand = {}
    for it in items:
        if it["size_mb"] > max_mb or it["size_mb"] <= 0:
            continue
        by_brand.setdefault(it["brand"], []).append(it)
    picked = []
    # 轮转取，保证品牌分散
    i = 0
    while len(picked) < limit:
        added = False
        for brand in sorted(by_brand):
            lst = by_brand[brand]
            if i < len(lst):
                picked.append(lst[i])
                added = True
                if len(picked) >= limit:
                    break
        if not added:
            break
        i += 1
        if i > per_brand:
            break
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--brand", default=None)
    ap.add_argument("--spread", action="store_true", help="按品牌分散挑选")
    ap.add_argument("--per-brand", type=int, default=2)
    ap.add_argument("--max-mb", type=float, default=40.0)
    ap.add_argument("--brands", default=None,
                    help="品牌白名单，逗号分隔（不区分大小写），如 Canon,Nikon,Sony")
    ap.add_argument("--out", default="test_data_raw2")
    args = ap.parse_args()

    items = fetch_all()
    print(f"样本库共 {len(items)} 个 RAW")

    if args.brands:
        want = [b.strip().lower() for b in args.brands.split(",") if b.strip()]
        items = [i for i in items if i["brand"].lower() in want]
        print(f"品牌白名单 {want}：{len(items)} 个")

    if args.brand:
        items = [i for i in items if i["brand"].lower() == args.brand.lower()]
        print(f"品牌 {args.brand}：{len(items)} 个")

    if args.download:
        if args.spread:
            targets = pick_spread(items, args.per_brand, args.limit, args.max_mb)
        else:
            targets = [i for i in items if i["size_mb"] <= args.max_mb][:args.limit]
        out_dir = ROOT / args.out
        out_dir.mkdir(parents=True, exist_ok=True)
        ok = fail = 0
        for t in targets:
            target = out_dir / _safe_name(t["name"])
            if target.exists():
                print(f"[skip] {t['name']}")
                continue
            try:
                data = _get(_norm_url(t["url"]), timeout=240)
                target.write_bytes(data)
                ok += 1
                print(f"[ok]   {t['brand']} {t['model']} | {t['name']} "
                      f"({len(data)/1e6:.1f}MB)")
            except Exception as e:
                fail += 1
                print(f"[x]    {t['name']}: {type(e).__name__} {e}")
        print(f"下载完成：成功 {ok} / 失败 {fail} → {out_dir}")
    else:
        for t in items[:args.limit]:
            print(f"  {t['brand']:14s} {t['model']:22s} {t['size_mb']:6.1f}MB  {t['name']}")


if __name__ == "__main__":
    main()
