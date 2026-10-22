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
"""照片堆叠（Stacks）回归测试：双格式栈 / 连拍栈 / 不合并规则 / 重入幂等 / 不删原图。

对照 photo_manager/core/stacks.py 的实现规则：
- 双格式栈：同目录 + 同 basename（去扩展名）的 RAW + 非 RAW 合并。
- 连拍栈：同目录 + 间隔 < 5s + dHash 汉明距离 ≤ 10 的连续张合并。
- detect_stacks 仅写元数据（photos.stack_id / stacks 表），绝不删除、绝不动文件。
"""
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.db import Database
from photo_manager.core import stacks


def _add(db: Database, **kw) -> int:
    """插入一张照片并返回其 id。缺省值给出可入库的最小非空集。"""
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
            kw.get("taken_at", "2025-01-01T10:00:00"),
            kw.get("sort_key", kw.get("taken_at", "2025-01-01T10:00:00")),
            kw.get("width", 1000),
            kw.get("height", 800),
            kw.get("phash"),
            kw.get("status", "indexed"),
        ),
    )
    return cur.lastrowid


class TestStacks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "s.db").connect()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _setup_duals_and_burst(self):
        # 连拍栈（3 张，间隔 2s，内容相似）
        p1 = _add(self.db, file_name="b1.jpg", taken_at="2025-01-01T10:00:00",
                  phash="0000000000000000", width=1000, height=800)
        p2 = _add(self.db, file_name="b2.jpg", taken_at="2025-01-01T10:00:02",
                  phash="0000000000000007", width=2000, height=1500)  # 面积最大 → 代表帧
        p3 = _add(self.db, file_name="b3.jpg", taken_at="2025-01-01T10:00:04",
                  phash="000000000000000f", width=800, height=600)
        # 双格式栈（RAW + JPG，同 stem）
        p4 = _add(self.db, file_name="IMG_0001.cr2", ext="cr2",
                  taken_at="2025-01-01T09:00:00", phash="1111111111111111",
                  width=4000, height=3000)
        p5 = _add(self.db, file_name="IMG_0001.jpg", ext="jpg",
                  taken_at="2025-01-01T09:00:01", phash="2222222222222222",
                  width=1920, height=1080)  # JPG → 代表帧
        # 不合并：不同目录、无伙伴、间隔过大
        p6 = _add(self.db, file_name="alone.jpg", folder_path="/home",
                  taken_at="2025-02-01T12:00:00", phash="3333333333333333")
        p7 = _add(self.db, file_name="g1.jpg", folder_path="/t2",
                  taken_at="2025-03-01T10:00:00", phash="4444444444444444")
        p8 = _add(self.db, file_name="g2.jpg", folder_path="/t2",
                  taken_at="2025-03-01T10:00:30", phash="4444444444444445")  # 间隔 30s > 5s
        self.db.conn.commit()
        return dict(p1=p1, p2=p2, p3=p3, p4=p4, p5=p5, p6=p6, p7=p7, p8=p8)

    def test_detect_stacks_counts(self):
        ids = self._setup_duals_and_burst()
        res = stacks.detect_stacks(self.db)
        # 2 个栈：连拍(3 张) + 双格式(2 张)；p6/p7/p8 不入栈
        self.assertEqual(res["stacks"], 2, "应检出 2 个栈")
        self.assertEqual(res["photos"], 5, "5 张照片入栈")
        self.assertEqual(stacks.stack_count(self.db), 2)

    def test_burst_stack_members_and_representative(self):
        ids = self._setup_duals_and_burst()
        stacks.detect_stacks(self.db)
        # 连拍栈通过 p1 定位（双格式先于连拍入库，故连拍栈 id 不固定）
        sid = self.db.conn.execute(
            "SELECT stack_id FROM photos WHERE id=?", (ids["p1"],)).fetchone()[0]
        members = stacks.stack_members(self.db, sid)
        member_ids = {m[0] for m in members}
        self.assertSetEqual(member_ids, {ids["p1"], ids["p2"], ids["p3"]})
        # 代表帧 = 面积最大者 p2
        rep = self.db.conn.execute(
            "SELECT representative_photo_id FROM stacks WHERE id=?", (sid,)).fetchone()[0]
        self.assertEqual(rep, ids["p2"])

    def test_dual_format_stack_and_representative(self):
        ids = self._setup_duals_and_burst()
        stacks.detect_stacks(self.db)
        # 找到含 p4/p5 的栈
        sid = self.db.conn.execute(
            "SELECT stack_id FROM photos WHERE id=?", (ids["p5"],)).fetchone()[0]
        members = {m[0] for m in stacks.stack_members(self.db, sid)}
        self.assertSetEqual(members, {ids["p4"], ids["p5"]})
        rep = self.db.conn.execute(
            "SELECT representative_photo_id FROM stacks WHERE id=?", (sid,)).fetchone()[0]
        self.assertEqual(rep, ids["p5"], "双格式优先 JPG 作代表帧")

    def test_non_stack_photos_unaffected(self):
        ids = self._setup_duals_and_burst()
        stacks.detect_stacks(self.db)
        for pid in (ids["p6"], ids["p7"], ids["p8"]):
            sid = self.db.conn.execute(
                "SELECT stack_id FROM photos WHERE id=?", (pid,)).fetchone()[0]
            self.assertIsNone(sid, "不应被合并入栈")

    def test_no_photo_deleted(self):
        """堆叠只写元数据，绝不能删除或移动任何照片（红线）。"""
        self._setup_duals_and_burst()
        before = self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing'").fetchone()[0]
        stacks.detect_stacks(self.db)
        after = self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing'").fetchone()[0]
        self.assertEqual(before, after, "照片总数不应因堆叠而减少")
        self.assertEqual(before, 8)

    def test_idempotent_rerun(self):
        self._setup_duals_and_burst()
        stacks.detect_stacks(self.db)
        stacks.detect_stacks(self.db)  # 重入应清空旧栈再重建，不翻倍
        self.assertEqual(stacks.stack_count(self.db), 2)
        all_rows = self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE stack_id IS NOT NULL").fetchone()[0]
        self.assertEqual(all_rows, 5)


if __name__ == "__main__":
    unittest.main()
