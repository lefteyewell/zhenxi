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
"""往年今日（On This Day）查询回归测试。

对照 photo_manager/core/search.py:on_this_day 的规则：
- 取拍摄于指定 月-日（MM-DD）的照片（sort_key/taken_at 同格式 YYYY-MM-DDTHH:MM:SS）。
- 排除今年（substr(...,1,4) != 今年）。
- 返回条目含 year 字段（int），供前端按年分组。
- 只查未缺失照片，不触碰原图/不删除。
"""
import datetime
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.db import Database
from photo_manager.core.search import on_this_day


def _add(db: Database, **kw) -> int:
    c = db.conn
    fname = kw["file_name"]
    ext = kw.get("ext") or fname.rsplit(".", 1)[-1].lower()
    cur = c.execute(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
        " file_mtime, taken_at, sort_key, width, height, perceptual_hash, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            kw.get("file_path", fname),
            fname,
            kw.get("folder_path", "/trip"),
            ext,
            kw.get("file_size", 1),
            kw.get("file_mtime", 1.0),
            kw.get("taken_at", "2020-06-15T10:00:00"),
            kw.get("sort_key", kw.get("taken_at", "2020-06-15T10:00:00")),
            kw.get("width", 1000),
            kw.get("height", 800),
            kw.get("phash"),
            kw.get("status", "indexed"),
        ),
    )
    return cur.lastrowid


class TestOnThisDay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "othisday.db").connect()
        # 用一个固定“今天”做确定性断言：构造一组照片，含今年与往年同月-日
        self.md = "06-15"  # MM-DD
        self.cur_year = str(datetime.date.today().year)
        # 往年同日（应命中）
        _add(self.db, file_name="a2019.jpg", taken_at="2019-06-15T09:00:00", phash="aaaa")
        _add(self.db, file_name="b2020.jpg", taken_at="2020-06-15T18:30:00", phash="bbbb")
        # 今年同日（应排除）
        _add(self.db, file_name="c_this.jpg",
             taken_at=f"{self.cur_year}-06-15T12:00:00", phash="cccc")
        # 其他月-日（不应命中）
        _add(self.db, file_name="d_other.jpg", taken_at="2018-07-04T12:00:00", phash="dddd")
        # 缺失状态的往年同日（不应命中）
        _add(self.db, file_name="e_missing.jpg", taken_at="2017-06-15T12:00:00",
             phash="eeee", status="missing")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_matches_same_month_day_excludes_current_year(self):
        rows = on_this_day(self.db, self.md)
        ids = {r["name"] for r in rows}
        self.assertIn("a2019.jpg", ids)
        self.assertIn("b2020.jpg", ids)
        self.assertNotIn("c_this.jpg", ids)   # 今年被排除
        self.assertNotIn("d_other.jpg", ids)  # 不同月-日
        self.assertNotIn("e_missing.jpg", ids)  # 缺失状态排除

    def test_year_field_present_and_correct(self):
        rows = on_this_day(self.db, self.md)
        by_name = {r["name"]: r for r in rows}
        self.assertEqual(by_name["a2019.jpg"]["year"], 2019)
        self.assertEqual(by_name["b2020.jpg"]["year"], 2020)

    def test_default_uses_today(self):
        # 默认 month_day="" 取今天；库里没有“今天”的照片，应为空且不报错
        rows = on_this_day(self.db, "")
        # 即便今天就是 06-15（极小概率），c_this.jpg 属今年也应被排除
        self.assertNotIn("c_this.jpg", {r["name"] for r in rows})

    def test_ascending_order(self):
        rows = on_this_day(self.db, self.md)
        years = [r["year"] for r in rows]
        self.assertEqual(years, sorted(years))


if __name__ == "__main__":
    unittest.main()
