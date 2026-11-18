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
"""迷你 FITS 读取器（零第三方依赖，纯 numpy）。

背景：ImageMagick 兜底清单里唯一值得补的常规格式是 FITS（天文）——
格式为 1981 年公开标准，结构极规整：2880 字节定长块 + 80 字符 ASCII
头部卡（BITPIX/NAXIS/BSCALE/BZERO）+ 裸像素数据（大端）。自研解析
约两百行即覆盖 99% 的真实文件，不再为它捆绑几十 MB 的 ImageMagick。

支持范围（"迷你"边界，明确不支持时返回 None 并在 error 信息中说明）：
- SIMPLE=T 主 HDU 与 XTENSION='IMAGE' 扩展 HDU（跳过 BINTABLE 等）
- BITPIX 8/16/32/64/-32/-64，BSCALE/BZERO 缩放偏移
- 2D 图像；3D 取首帧；NAXIS3=3 的 RGB 数据按彩色处理
- 输出统一归一化为 uint8（8 位直用；高位深按 1%~99.5% 分位数拉伸——
  天文数据的动态范围远超显示区间的惯例处理）
不支持：压缩图像（Rice/GZIP tile 存在 BINTABLE 里，本解析器按表跳过）、
随机组记录、奇异/损坏文件——这些仍可走 ImageMagick 兜底（若系统装有）。
"""
from __future__ import annotations

import os

import numpy as np

BLOCK = 2880
CARD = 80

_PIX = {
    8: "u1", 16: ">i2", 32: ">i4", 64: ">i8",
    -32: ">f4", -64: ">f8",
}


def _card_value(raw: str):
    """解析一张卡片的值：字符串去引号，T/F 转布尔，数字转 int/float。"""
    v = raw.split("/", 1)[0].strip()
    if not v:
        return None
    if v.startswith("'"):
        # FITS 字符串：单引号，内部 '' 转义为 '
        end = 1
        buf = []
        while end < len(v):
            if v[end] == "'":
                if end + 1 < len(v) and v[end + 1] == "'":
                    buf.append("'")
                    end += 2
                    continue
                break
            buf.append(v[end])
            end += 1
        return "".join(buf).rstrip()
    if v == "T":
        return True
    if v == "F":
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v.replace("D", "E").replace("d", "e"))
    except ValueError:
        return None


def _read_header(data: bytes, pos: int) -> tuple[dict, int] | None:
    """从 pos 起读一个完整头部（至 END 卡），返回 ({键: 值}, 头部总字节数)。"""
    keys: dict[str, object] = {}
    off = pos
    n = len(data)
    while off + BLOCK <= n:
        for i in range(BLOCK // CARD):
            card = data[off + i * CARD: off + (i + 1) * CARD]
            text = card.decode("ascii", errors="replace")
            if text.startswith("END") and text[3:].strip() == "":
                return keys, off + BLOCK - pos
            key = text[:8].strip()
            if key and len(text) > 9 and text[8] == "=":
                keys[key] = _card_value(text[9:])
        off += BLOCK
    return None


def read_fits_array(path: str) -> tuple[np.ndarray, str] | None:
    """读 FITS 首个图像 HDU → uint8 数组（2D 灰度或 3D RGB）。

    返回 (数组, "") 或 (None, 原因说明)。调用方按 None/原因决定兜底。
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None, "文件不可读"
    if len(data) < BLOCK or not data.startswith(b"SIMPLE  ="):
        return None, "非 FITS 文件"
    pos = 0
    while pos + BLOCK <= len(data):
        hdr = _read_header(data, pos)
        if hdr is None:
            return None, "头部不完整"
        keys, hsize = hdr
        pos += hsize
        bitpix = keys.get("BITPIX")
        naxis = keys.get("NAXIS") or 0
        axes = [keys.get(f"NAXIS{i}") or 0 for i in range(1, naxis + 1)]
        if bitpix not in _PIX or naxis == 0 or 0 in axes:
            # 空主 HDU / 非图像扩展 / 表格：跳到下一个 HDU
            if bitpix in _PIX and naxis:
                pcount = keys.get("PCOUNT") or 0
                gcount = keys.get("GCOUNT") or 1
                total = abs(bitpix) // 8 * gcount * (pcount + int(np.prod(axes)))
                pos += (total + BLOCK - 1) // BLOCK * BLOCK
            continue
        pcount = keys.get("PCOUNT") or 0
        gcount = keys.get("GCOUNT") or 1
        npix = int(np.prod(axes))
        total = abs(bitpix) // 8 * gcount * (pcount + npix)
        end = pos + total
        if end > len(data):
            return None, "数据被截断"
        arr = np.frombuffer(data, dtype=_PIX[bitpix], count=npix,
                            offset=pos + pcount * abs(bitpix) // 8 * gcount)
        bscale = keys.get("BSCALE")
        bzero = keys.get("BZERO")
        if bscale or bzero:
            arr = arr.astype(np.float64) * (bscale if bscale else 1.0) \
                + (bzero if bzero else 0.0)
        pos += (total + BLOCK - 1) // BLOCK * BLOCK
        # 形状：FITS NAXIS1 是最快轴（宽度）
        if naxis == 1:
            return _to_u8(arr), ""
        if naxis == 2:
            return _to_u8(arr.reshape(axes[1], axes[0])), ""
        if naxis == 3:
            if axes[2] == 3:
                # RGB 平面：FITS 存 (w, h, 3)，转 (h, w, 3) RGB
                rgb = arr.reshape(axes[2], axes[1], axes[0]).transpose(1, 2, 0)
                return _to_u8(rgb), ""
            # 取首帧
            return _to_u8(arr.reshape(axes[2], axes[1], axes[0])[0]), ""
        return None, f"不支持的维度 NAXIS={naxis}"
    return None, "未找到图像 HDU"


def _to_u8(arr: np.ndarray) -> np.ndarray:
    """归一化为 uint8：8 位直用；高位深按 1%~99.5% 分位数拉伸。"""
    arr = np.asarray(arr)
    if arr.dtype == np.uint8:
        return arr
    arr = arr.astype(np.float64)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return np.zeros(arr.shape, dtype=np.uint8)
    lo = float(np.percentile(finite, 1.0))
    hi = float(np.percentile(finite, 99.5))
    if hi <= lo:
        lo, hi = float(finite.min()), float(finite.min()) + 1.0
    out = (arr - lo) / (hi - lo) * 255.0
    return np.clip(out, 0, 255).astype(np.uint8)
