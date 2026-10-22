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
"""多线程持久重试下载 Commons 活动照片（wsrv 通路间歇放行）。

复用 fetch_commons_event_photos 的候选清单与 URL 构造；
8 线程各自重试（GFW 式 TLS 重置呈波状放行，窗口一到批量成功），
全局达到 50 张即停，结束后重建 manifest.csv / ATTRIBUTIONS.md。
"""
import csv
import random
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_commons_event_photos import (  # noqa: E402
    EVENTS, OUT, UA, sanitize, wsrv_url)

TARGET = 50
DEADLINE_SEC = 50 * 60
WORKERS = 8

lock = threading.Lock()
state = {"ok": 0, "stop": False}


def dest_for(folder: str, title: str) -> Path:
    return OUT / folder / f"{folder[3:5]}_{sanitize(title[:60])}.jpg"


def build_queue():
    """返回 [(folder, title, dest, event_remaining_allowance)]，
    每活动按目标数预留（含已存在文件）。"""
    q = []
    per_event_have = {}
    for folder, want, titles in EVENTS:
        edir = OUT / folder
        edir.mkdir(exist_ok=True)
        have = 0
        for title in titles:
            d = dest_for(folder, title)
            ok_existing = False
            if d.exists() and d.stat().st_size > 30_000:
                try:
                    with Image.open(d) as im:
                        im.load()
                    if min(im.size) >= 1080:
                        ok_existing = True
                except Exception:  # noqa: BLE001
                    pass
            if ok_existing:
                have += 1
            else:
                q.append((folder, title, d))
        per_event_have[folder] = have
        # 只保留 (want - have) 个新文件的任务量（多留 2 个余量防失败）
        keep = max(0, want - have) + 2
        # 队列按原顺序；把超出配额的任务标记为备用（放到最后）
        q_main = [t for t in q if t[0] == folder][:keep]
        q_spare = [t for t in q if t[0] == folder][keep:]
        q = [t for t in q if t[0] != folder]
        q.extend(q_main + q_spare)
    return q, per_event_have


def worker(item):
    folder, title, dest = item
    if state["stop"]:
        return None
    url = wsrv_url(title)
    deadline = time.time() + DEADLINE_SEC
    attempt = 0
    while time.time() < deadline and not state["stop"]:
        attempt += 1
        if _try(url, dest):
            with Image.open(dest) as im:
                im.load()
                w, h = im.size
            if min(w, h) < 1080:
                dest.unlink(missing_ok=True)
                print(f"[drop] {title[:50]} too small {w}x{h}", flush=True)
                return None
            with lock:
                state["ok"] += 1
                ok = state["ok"]
                if ok >= TARGET:
                    state["stop"] = True
            print(f"[OK #{ok}] {folder} {title[:52]} {w}x{h} "
                  f"(tries={attempt})", flush=True)
            return item
        time.sleep(random.uniform(6, 14))
    return None


def _try(url, dest) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with OPENER.open(req, timeout=45) as resp, \
                open(dest, "wb") as fh:
            fh.write(resp.read())
        return dest.stat().st_size > 30_000
    except Exception:  # noqa: BLE001
        return False


def finalize():
    rows = []
    for folder, _want, titles in EVENTS:
        for title in titles:
            d = dest_for(folder, title)
            if d.exists() and d.stat().st_size > 30_000:
                try:
                    with Image.open(d) as im:
                        im.load()
                        w, h = im.size
                except Exception:  # noqa: BLE001
                    continue
                rows.append([folder, d.name, title, f"{w}x{h}",
                             d.stat().st_size,
                             "https://commons.wikimedia.org/wiki/File:"
                             + urllib.parse.quote(title)])
    with open(OUT / "manifest.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        wtr = csv.writer(f)
        wtr.writerow(["event", "file", "commons_title", "size_px",
                      "bytes", "source_page"])
        wtr.writerows(rows)
    with open(OUT / "ATTRIBUTIONS.md", "w", encoding="utf-8") as f:
        f.write("# 测试图片来源与署名\n\n"
                "全部照片来自 Wikimedia Commons（CC BY / CC BY-SA / 公有领域等"
                "自由授权），仅作本地软件测试用途。\n"
                "原始文件页与作者/许可证见 manifest.csv 的 source_page 列。\n\n")
        cur = None
        for r in rows:
            if r[0] != cur:
                cur = r[0]
                f.write(f"\n## {cur}\n\n")
            f.write(f"- {r[2]} — [{r[3]}]({r[5]})\n")
    return rows


def main() -> int:
    q, per_event_have = build_queue()
    print(f"queue={len(q)} 已有: "
          + ", ".join(f"{k}:{v}" for k, v in per_event_have.items()),
          flush=True)
    done = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(worker, item) for item in q]
        for fu in as_completed(futs):
            r = fu.result()
            if r:
                done.append(r)
    rows = finalize()
    n = len(rows)
    print(f"\nTOTAL={n}", flush=True)
    per = {}
    for r in rows:
        per[r[0]] = per.get(r[0], 0) + 1
    for k in sorted(per):
        print(f"  {k}: {per[k]}", flush=True)
    return 0 if n >= TARGET else 2


if __name__ == "__main__":
    sys.exit(main())
