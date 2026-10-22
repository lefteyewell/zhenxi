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
"""事件时间聚类：时间间隔为主信号，文件夹名辅助命名，GPS 取中位。"""
from __future__ import annotations

import re
import statistics
import time
from datetime import datetime

from photo_manager.core.db import Database

DATE_PREFIX = re.compile(r"^\d{4}[-_.]\d{2}[-_.]\d{2}_?")


def _basename(folder_path: str) -> str:
    name = folder_path.rstrip("/").rsplit("/", 1)[-1]
    name = DATE_PREFIX.sub("", name)
    return name.strip("_- ") or folder_path.rsplit("/", 1)[-1]


class EventClusterer:
    def __init__(self, db: Database, gap_hours: float = 4.0):
        self.db = db
        self.gap_hours = gap_hours

    def run(self, progress_cb=None, cancel=None) -> dict:
        t0 = time.perf_counter()
        rows = self.db.conn.execute(
            "SELECT id, taken_at, gps_lat, gps_lon, folder_path FROM photos"
            " WHERE taken_at IS NOT NULL AND taken_at != ''"
            " AND status != 'missing' ORDER BY taken_at"
        ).fetchall()
        if not rows:
            return {"events": 0, "photos": 0, "sec": 0.0}

        def parse(ts: str):
            """解析拍摄时间；非法/无法解析返回 None（跳过该行，不中断聚类）。"""
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None

        # 预处理：解析一次并缓存。原实现在循环里对每条重复 parse 两次
        # （当前行 + 上一行），大库下是纯浪费；这里顺带剔除无法解析的行。
        parsed: list = []  # [(row, datetime)]
        for r in rows:
            dt = parse(r[1])
            if dt is not None:
                parsed.append((r, dt))
        if not parsed:
            return {"events": 0, "photos": 0, "sec": 0.0}

        events = []  # (start, end, photo_ids, lat, lon, folders)
        cur = [parsed[0][0]]
        prev_dt = parsed[0][1]
        for r, dt in parsed[1:]:
            if cancel and cancel():
                break
            gap = (dt - prev_dt).total_seconds() / 3600.0
            if gap > self.gap_hours:
                events.append(cur)
                cur = [r]
            else:
                cur.append(r)
            prev_dt = dt
        events.append(cur)

        conn = self.db.conn
        conn.execute("DELETE FROM event_photos")
        conn.execute("DELETE FROM events")
        for ev in events:
            ids = [r[0] for r in ev]
            lats = [r[2] for r in ev if r[2] is not None]
            lons = [r[3] for r in ev if r[3] is not None]
            folders = [r[4] for r in ev]
            start = ev[0][1][:10]
            end = ev[-1][1][:10]
            title = _basename(max(set(folders), key=folders.count))
            if len(title) > 40:
                title = title[:40]
            if len({start, end}) == 2:
                title = f"{title}（{start}~{end}）" if title else f"{start}~{end}"
            elif not title:
                title = start
            cursor = conn.execute(
                "INSERT INTO events(start_at, end_at, title, center_lat, center_lon, photo_count)"
                " VALUES (?,?,?,?,?,?)",
                (
                    start, end, title,
                    round(statistics.median(lats), 7) if lats else None,
                    round(statistics.median(lons), 7) if lons else None,
                    len(ids),
                ),
            )
            eid = cursor.lastrowid
            conn.executemany(
                "INSERT INTO event_photos(event_id, photo_id) VALUES (?,?)",
                [(eid, i) for i in ids],
            )
            if progress_cb:
                progress_cb(len(events), len(events))
        conn.commit()
        return {
            "events": len(events),
            # 用实际参与聚类的张数（原用 len(rows)，会把时间无法解析、
            # 被跳过的照片也算进去，导致统计偏大）
            "photos": len(parsed),
            "sec": round(time.perf_counter() - t0, 3),
        }
