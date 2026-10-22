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
"""库完整性校验（#7）回归测试。

校验是**只读**的：只比对数据库索引与磁盘，不改状态、不删记录、不动原图。
四类问题：missing（文件没了）/ changed（大小或 mtime 与库不符）/
thumbMissing（缩略图丢了）/ error（分析失败）。

仅为 changed / thumbMissing / error 提供重跑分析修复；missing 必须留给用户
到回收站决定，程序不擅自清除（不删除红线）。
"""
import os
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.db import Database
from photo_manager.core.integrity import REPAIRABLE, check_integrity


def _write(path, data: bytes = b"jpeg-bytes-1234567890"):
    Path(path).write_bytes(data)
    st = os.stat(str(path))
    return st.st_size, st.st_mtime


def _add(db: Database, **kw) -> int:
    c = db.conn
    cur = c.execute(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
        " file_mtime, taken_at, sort_key, width, height, rating, archived, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            kw["file_path"],
            kw["file_name"],
            kw.get("folder_path", str(Path(kw["file_path"]).parent)),
            kw.get("ext", "jpg"),
            kw.get("file_size", 1),
            kw.get("file_mtime", 1.0),
            kw.get("taken_at", "2020-06-15T10:00:00"),
            kw.get("sort_key", "2020-06-15T10:00:00"),
            kw.get("width", 1000),
            kw.get("height", 800),
            kw.get("rating", 0),
            kw.get("archived", 0),
            kw.get("status", "indexed"),
        ),
    )
    return cur.lastrowid


class TestIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = Database(self.root / "integrity.db").connect()

        # 1) 完全正常：文件在、size/mtime 相符、缩略图在、已索引
        p = self.root / "ok.jpg"
        size, mtime = _write(p)
        self.ok = _add(self.db, file_name="ok.jpg", file_path=str(p),
                       file_size=size, file_mtime=mtime)
        self._set(self.ok, thumb=self.root / "th_ok.jpg", status="indexed")
        _write(self.root / "th_ok.jpg", b"thumb")

        # 2) 文件已被系统外删除
        self.gone = _add(self.db, file_name="gone.jpg",
                         file_path=str(self.root / "gone.jpg"))
        self._set(self.gone, thumb=self.root / "th_gone.jpg", status="indexed")
        _write(self.root / "th_gone.jpg", b"thumb")

        # 3) 文件被改动：库里记的 size 与磁盘不符
        p = self.root / "changed.jpg"
        size, mtime = _write(p)
        self.changed = _add(self.db, file_name="changed.jpg", file_path=str(p),
                            file_size=size + 999, file_mtime=mtime)
        self._set(self.changed, thumb=self.root / "th_ch.jpg", status="indexed")
        _write(self.root / "th_ch.jpg", b"thumb")

        # 4) 原图在但缩略图丢了
        p = self.root / "nothumb.jpg"
        size, mtime = _write(p)
        self.nothumb = _add(self.db, file_name="nothumb.jpg", file_path=str(p),
                            file_size=size, file_mtime=mtime)
        self._set(self.nothumb, thumb=self.root / "never_written.jpg", status="indexed")

        # 5) 分析失败
        p = self.root / "err.jpg"
        size, mtime = _write(p)
        self.err = _add(self.db, file_name="err.jpg", file_path=str(p),
                        file_size=size, file_mtime=mtime)
        self._set(self.err, thumb=self.root / "th_err.jpg", status="error")
        _write(self.root / "th_err.jpg", b"thumb")

        self.db.conn.commit()

    def _set(self, pid, thumb=None, status=None):
        self.db.conn.execute(
            "UPDATE photos SET thumbnail_path=?, status=? WHERE id=?",
            (str(thumb) if thumb else None, status, pid))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    # ---- 四类问题各识别一张 ----
    def test_total_and_ok(self):
        rep = check_integrity(self.db)
        self.assertEqual(rep["total"], 5)
        self.assertEqual(rep["ok"], 1)

    def test_missing(self):
        rep = check_integrity(self.db)
        self.assertEqual(rep["counts"]["missing"], 1)
        self.assertEqual(rep["ids"]["missing"], [self.gone])

    def test_changed(self):
        rep = check_integrity(self.db)
        self.assertEqual(rep["counts"]["changed"], 1)
        self.assertEqual(rep["ids"]["changed"], [self.changed])

    def test_thumb_missing(self):
        rep = check_integrity(self.db)
        self.assertEqual(rep["counts"]["thumbMissing"], 1)
        self.assertEqual(rep["ids"]["thumbMissing"], [self.nothumb])

    def test_error_status(self):
        rep = check_integrity(self.db)
        self.assertEqual(rep["counts"]["error"], 1)
        self.assertEqual(rep["ids"]["error"], [self.err])

    # ---- 红线：校验必须只读 ----
    def test_read_only_status_unchanged(self):
        before = dict(self.db.conn.execute(
            "SELECT id, status FROM photos").fetchall())
        check_integrity(self.db)
        after = dict(self.db.conn.execute(
            "SELECT id, status FROM photos").fetchall())
        self.assertEqual(before, after)

    def test_idempotent(self):
        a = check_integrity(self.db)
        b = check_integrity(self.db)
        self.assertEqual(a["counts"], b["counts"])
        self.assertEqual(a["ids"], b["ids"])

    # ---- 缺失项不可自动修复 ----
    def test_missing_not_repairable(self):
        self.assertNotIn("missing", REPAIRABLE)
        self.assertIn("changed", REPAIRABLE)
        self.assertIn("thumbMissing", REPAIRABLE)
        self.assertIn("error", REPAIRABLE)

    # ---- 文件恢复后不再报缺失 ----
    def test_restored_file_no_longer_missing(self):
        rep = check_integrity(self.db)
        self.assertIn(self.gone, rep["ids"]["missing"])
        # 模拟文件回到原位
        p = self.root / "gone.jpg"
        size, mtime = _write(p)
        self.db.conn.execute(
            "UPDATE photos SET file_size=?, file_mtime=?, status='indexed' WHERE id=?",
            (size, mtime, self.gone))
        self.db.conn.commit()
        rep2 = check_integrity(self.db)
        self.assertNotIn(self.gone, rep2["ids"]["missing"])


if __name__ == "__main__":
    unittest.main()
