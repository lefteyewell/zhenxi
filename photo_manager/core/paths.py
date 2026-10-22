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
"""库内相对存储路径的解析（0.5.51）。

背景：缩略图/大图预览/视频关键帧等派生文件的路径，库内只存**相对数据
目录**的形式（如 "thumbs/6c/5fa2b858e3fcb4.jpg"）。这样整个程序目录
（便携软件）可随意移动/改名，库随目录走，派生路径不失效。

历史：0.5.50 及以前存绝对路径，程序目录一移动全库缩略图断链成空白格
（用户实测“同文件夹跳转中间栏空白”即此现象——缩略图绝对路径指向旧包位置）。
"""
from __future__ import annotations

from pathlib import Path


def data_dir_of(db_path: str | Path) -> Path:
    """DB 所在目录即数据目录（data/）。"""
    return Path(db_path).resolve().parent


def resolve_data_path(db_path: str | Path, stored: str | None) -> str:
    """库内存储值 → 绝对路径。

    - 绝对路径：原样返回（兼容 0.5.50 前的历史数据）；
    - 相对路径：按 DB 所在目录解析（thumbs/…、previews/…、frames/…）；
    - 空值：返回 ""。
    """
    if not stored:
        return ""
    p = Path(str(stored))
    if p.is_absolute():
        return str(p)
    return str(data_dir_of(db_path) / p)
