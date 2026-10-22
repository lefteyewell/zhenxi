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
"""校验 test_data_cn_meetings 全部 jpg，并生成总览拼图便于目检。"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "test_data_cn_meetings")


def font():
    for p in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(p, 16)
        except Exception:
            continue
    return ImageFont.load_default()


def main() -> int:
    files = sorted([p for p in OUT.glob("*/*.jpg") if not p.name.startswith("_")])
    print(f"共 {len(files)} 张", flush=True)
    bad = []
    thumbs = []
    f = font()
    for p in files:
        try:
            im = Image.open(p).convert("RGB")
            w, h = im.size
            short = min(w, h)
            status = "OK" if short >= 1080 else "SHORT"
            print(f"{p.parent.name}/{p.name}: {w}x{h} [{status}]", flush=True)
            if short < 1080:
                bad.append(p)
            im.thumbnail((220, 220), Image.LANCZOS)
            thumbs.append((p, im))
        except Exception as e:  # noqa: BLE001
            print(f"{p}: ERROR {e}", flush=True)
            bad.append(p)

    # 拼图 10 列 x 5 行
    cols, cell = 10, 240
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 24)), (235, 235, 235))
    dr = ImageDraw.Draw(sheet)
    for i, (p, im) in enumerate(thumbs):
        r, c = divmod(i, cols)
        x, y = c * cell, r * (cell + 24)
        sheet.paste(im, (x + (cell - im.width) // 2, y + 24 + (cell - 220) // 2))
        label = f"{i:02d} {p.parent.name[3:6]}/{p.name}"
        dr.text((x + 3, y + 2), label, fill=(0, 0, 0), font=f)
    sheet.save(OUT / "_contact_sheet_final.jpg", "JPEG", quality=88)
    print(f"坏图 {len(bad)} 张; 拼图: {OUT / '_contact_sheet_final.jpg'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
