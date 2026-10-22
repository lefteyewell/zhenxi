# PhotoManager - 照片管理系统
# Copyright (C) 2026 蒙汗药
# SPDX-License-Identifier: GPL-3.0-or-later
"""0.5.64 损坏文件标记（decode_error）链路测试。

依赖 SampleRAW/ 下的真实 RAW 样张（截断的 ORF 与完好的 ARW/CR3）；
样张缺失时整类跳过（CI/他机无样张不误报）。
覆盖：
  1) make_preview_ex 对截断 RAW 返回 state="fallback"（内嵌兜底）
  2) make_preview_ex 对完好 RAW 返回 "ok"/"unverified"
  3) deep_decode_check 对截断 RAW 写 decode_error=1，完好 RAW 不标
  4) check_integrity 报告含 decodeError 类别且计数正确
"""
import os
import shutil
import sqlite3
import tempfile
import unittest

sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in os.sys.path:
    os.sys.path.insert(0, sys_path)

from photo_manager.core import extractor, integrity  # noqa: E402

SAMPLE_DIR = os.path.join(sys_path, "SampleRAW")
ORF_TRUNC = os.path.join(SAMPLE_DIR, "ORF_Olympus__RAW_OLYMPUS_C5050Z.ORF")
ARW_OK = os.path.join(SAMPLE_DIR, "ARW_Sony2__DSC00009.ARW")


@unittest.skipUnless(os.path.exists(ORF_TRUNC) and os.path.exists(ARW_OK),
                     "需要 SampleRAW 样张")
class TestDecodeError(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "t.db")
        self.conn = sqlite3.connect(self.db_path)
        # 最小 photos 表（与生产 schema 相关列对齐）
        self.conn.executescript("""
            CREATE TABLE photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT, ext TEXT, status TEXT DEFAULT 'indexed',
                file_size INTEGER, file_mtime REAL, thumbnail_path TEXT,
                decode_error INTEGER NOT NULL DEFAULT 0
            );
        """)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _insert(self, path):
        cur = self.conn.execute(
            "INSERT INTO photos(file_path, ext, status) VALUES (?,?, 'indexed')",
            (path, os.path.splitext(path)[1].lower()))
        self.conn.commit()
        return cur.lastrowid

    def test_preview_state_fallback_on_truncated(self):
        out = os.path.join(self.tmp, "orf.jpg")
        r = extractor.make_preview_ex(ORF_TRUNC, out)
        self.assertIsNotNone(r, "截断 ORF 应经内嵌兜底出预览")
        self.assertEqual(r[2], "fallback")

    def test_preview_state_ok_on_healthy(self):
        out = os.path.join(self.tmp, "arw.jpg")
        r = extractor.make_preview_ex(ARW_OK, out)
        self.assertIsNotNone(r)
        self.assertIn(r[2], ("ok", "unverified"))

    def test_deep_decode_check_marks_damaged(self):
        bad = self._insert(ORF_TRUNC)
        good = self._insert(ARW_OK)
        rep = integrity.deep_decode_check(self.conn)
        self.assertGreaterEqual(rep["scanned"], 2)
        self.assertIn(bad, rep["damaged_ids"])
        self.assertNotIn(good, rep["damaged_ids"])
        flag_bad = self.conn.execute(
            "SELECT decode_error FROM photos WHERE id=?", (bad,)).fetchone()[0]
        flag_good = self.conn.execute(
            "SELECT decode_error FROM photos WHERE id=?", (good,)).fetchone()[0]
        self.assertEqual(flag_bad, 1)
        self.assertEqual(flag_good, 0)

    def test_integrity_reports_decode_error(self):
        pid = self._insert(ORF_TRUNC)
        self.conn.execute(
            "UPDATE photos SET decode_error=1 WHERE id=?", (pid,))
        self.conn.commit()

        class _DB:  # check_integrity 只用 .conn
            conn = self.conn

        rep = integrity.check_integrity(_DB())
        self.assertEqual(rep["counts"]["decodeError"], 1)
        self.assertIn(pid, rep["ids"]["decodeError"])


if __name__ == "__main__":
    unittest.main()
