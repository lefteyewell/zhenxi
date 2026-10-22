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
"""把一批 RAW 解码并拼成联系表（contact sheet），便于快速目视筛选内容。

用途：RAW 样本库（如 raw.pixls.us）不提供内容描述，下载后无法判断
哪些含人物、哪些含招牌/横幅文字。本脚本解码所有 RAW 缩略图并拼成一张
网格大图，人工（或视觉模型）看一眼即可分类。

用法:
    python tools/preview_raw.py --src test_data_raw2 [--cols 6] [--cell 300]
输出:
    <src>/_preview/contact_sheet.jpg  以及单张预览 <src>/_preview/NN.jpg
"""
import argparse
import io
import sys
from pathlib import Path

import numpy as np
import rawpy
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent

RAW_EXT = {".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".orf",
           ".rw2", ".raw", ".raf", ".pef", ".ptx", ".dng", ".3fr", ".fff", ".iiq",
           ".rwl", ".mrw", ".mdc", ".mos", ".k25", ".kdc", ".dcr", ".x3f", ".erf",
           ".mef", ".cap", ".dcs", ".drf", ".gpr", ".srw", ".tif"}


def decode_thumb(path: Path):
    """返回 PIL.Image 或 None。优先内嵌缩略图，失败则完整解码降采样。"""
    try:
        with rawpy.imread(str(path)) as r:
            try:
                t = r.extract_thumb()
                if t is not None and getattr(t, "data", None) is not None:
                    if t.format == rawpy.ThumbFormat.JPEG:
                        return Image.open(io.BytesIO(t.data)).convert("RGB")
                    arr = np.asarray(t.data)
                    if arr.ndim == 3:
                        return Image.fromarray(arr).convert("RGB")
            except Exception:
                pass
            rgb = r.postprocess(half_size=True, use_camera_wb=True,
                                no_auto_bright=False, output_bps=8)
            return Image.fromarray(rgb).convert("RGB")
    except Exception as e:
        print(f"[decode-fail] {path.name}: {type(e).__name__} {e}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="test_data_raw2")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--cell", type=int, default=300)
    args = ap.parse_args()

    src = ROOT / args.src
    files = sorted([p for p in src.iterdir() if p.suffix.lower() in RAW_EXT])
    if not files:
        print("未找到 RAW 文件:", src)
        return 1

    out_dir = src / "_preview"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
    except Exception:
        font = ImageFont.load_default()

    thumbs, labels, ok_names = [], [], []
    for i, p in enumerate(files, 1):
        img = decode_thumb(p)
        if img is None:
            labels.append(f"{i:02d} {p.name[:22]} [解码失败]")
            thumbs.append(None)
            continue
        img.thumbnail((args.cell, args.cell), Image.LANCZOS)
        single = out_dir / f"{i:02d}.jpg"
        img.convert("RGB").save(single, "JPEG", quality=82)
        thumbs.append(img)
        ok_names.append(p.name)
        labels.append(f"{i:02d} {p.name[:24]}")
        print(f"[ok] {i:02d} {p.name}  {img.width}x{img.height}")

    # 拼联系表
    cols = args.cols
    rows = (len(thumbs) + cols - 1) // cols
    cw, ch = args.cell, args.cell + 24
    sheet = Image.new("RGB", (cols * cw, rows * ch), (245, 245, 245))
    dr = ImageDraw.Draw(sheet)
    for idx, img in enumerate(thumbs):
        r, c = divmod(idx, cols)
        x, y = c * cw, r * ch
        if img is None:
            dr.rectangle([x + 4, y + 24, x + cw - 4, y + ch - 4], fill=(220, 220, 220))
        else:
            off = ((cw - img.width) // 2, 24 + (args.cell - img.height) // 2)
            sheet.paste(img, (x + off[0], y + off[1]))
        dr.text((x + 4, y + 3), labels[idx], fill=(20, 20, 20), font=font)
    sheet_path = out_dir / "contact_sheet.jpg"
    sheet.save(sheet_path, "JPEG", quality=88)
    print(f"\n联系表: {sheet_path}  ({sheet.width}x{sheet.height})")
    print(f"成功解码 {len(ok_names)}/{len(files)}")
    for i, n in enumerate(ok_names, 1):
        print(f"  {i:02d} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
