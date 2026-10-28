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
"""弱机适配：按可用内存自动分档 workers / MAX_DIM，可用 PM_* 环境变量覆盖。

规则（RAM 分档）：
  >= 8 GB  -> 4 进程，MAX_DIM 3000
  4~8 GB   -> 2 进程，MAX_DIM 2500
  < 4 GB   -> 1 进程，MAX_DIM 2000
"""
from __future__ import annotations

import os


def available_ram_gb() -> float:
    """探测可用物理内存（GB）。Windows 用 ctypes；Linux 读 /proc/meminfo。"""
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return st.ullAvailPhys / (1024**3)
        elif os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", encoding="ascii", errors="ignore") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) / (1024 * 1024)
    except Exception:
        pass
    return 8.0


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip())
    except ValueError:
        return default


def auto_workers() -> int:
    """按内存与显式覆盖决定进程数。"""
    ov = _env_int("PM_MAX_WORKERS", 0)
    if ov > 0:
        return ov
    ram = available_ram_gb()
    if ram >= 8:
        return 4
    if ram >= 4:
        return 2
    return 1


def analysis_workers(mode: str = "auto", custom: int = 0) -> int:
    """分析任务进程数（0.6.9 设置项"分析并行度"）。

    auto（默认）：内存档位 + CPU 留 2 核钳制取小——保 UI 始终可操作。
    full（全速）：不预留 UI 核（占满核），内存档位放宽
                  （≥16GB → 8、≥8GB → 6，其余同 auto），允许用户提高利用率。
    custom：用户指定进程数（1~16，负载后果自负）。
    无参调用等价 auto（兼容旧调用点）。"""
    nproc = os.cpu_count() or 4
    if mode == "custom":
        return max(1, min(int(custom or 1), 16))
    if mode == "full":
        ram = available_ram_gb()
        cap = 8 if ram >= 16 else (6 if ram >= 8 else auto_workers())
        return max(1, min(max(auto_workers(), cap), nproc))
    return max(1, min(auto_workers(), max(1, nproc - 2)))


def max_dim() -> int:
    """人脸检测前图像最长边上限（像素），可 PM_MAX_DIM 覆盖。"""
    ov = _env_int("PM_MAX_DIM", 0)
    if ov > 0:
        return ov
    ram = available_ram_gb()
    if ram >= 8:
        return 3000
    if ram >= 4:
        return 2500
    return 2000


def set_files_readonly(paths: list[str], lock: bool) -> tuple[int, int]:
    """把一组文件设为/解除只读（只改文件系统属性，不动内容与库记录）。

    返回 (成功数, 跳过数)。跳过 = 文件缺失、被占用或无权限。
    Windows：只读位；POSIX：0o444 / 0o644。目录一律不碰。
    """
    import stat

    ok = skip = 0
    mode = 0o444 if lock else 0o644
    for p in paths:
        try:
            if not p or not os.path.isfile(p):
                skip += 1
                continue
            cur = os.stat(p).st_mode
            if lock and not (cur & stat.S_IWRITE):
                ok += 1  # 已是只读，视为成功
                continue
            os.chmod(p, mode)
            ok += 1
        except OSError:
            skip += 1
    return ok, skip
