# -*- coding: utf-8 -*-
# PhotoManager - 照片管理系统
# Copyright (C) 2026 蒙汗药
# SPDX-License-Identifier: GPL-3.0-or-later
"""0.6.20 回归测试：导出历史（「已导出」页数据源）。

缺陷背景（麒麟真机用户反馈）：exportProcessed 的免转码快速路径
（原格式+原始分辨率，最常用）此前只复制文件、漏写 export_records，
导致导出后「已导出」页永远无记录。本文件锁定该行为。
"""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from photo_manager.core.db import Database
from photo_manager.ui.library_bridge import LibraryBridge


class ExportHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "lib.db")).connect()
        self.bridge = LibraryBridge(os.path.join(self.tmp.name, "lib.db"))
        src = os.path.join(self.tmp.name, "src")
        os.makedirs(src)
        p1 = os.path.join(src, "a.jpg")
        p2 = os.path.join(src, "b.jpg")
        Image.new("RGB", (64, 48), (200, 50, 50)).save(p1)
        Image.new("RGB", (64, 48), (50, 200, 50)).save(p2)
        c = self.db.conn
        self.pids = []
        for p in (p1, p2):
            c.execute(
                "INSERT INTO photos(file_path, file_name, folder_path, ext,"
                " file_size, file_mtime, taken_at, sort_key, status)"
                " VALUES (?,?,?,?,?,?,?,?, 'indexed')",
                (p, os.path.basename(p), src, ".jpg",
                 os.path.getsize(p), 100.0, "2025-03-02T10:00:00",
                 "2025-03-02T10:00:00"))
            c.commit()
            self.pids.append(
                c.execute("SELECT id FROM photos WHERE file_path=?",
                          (p,)).fetchone()[0])
        self.dest = os.path.join(self.tmp.name, "desk")

    def tearDown(self):
        self.bridge.close()
        self.db.close()
        self.tmp.cleanup()

    def _wait_export_done(self):
        for _ in range(100):
            if self.bridge._busy == 0:
                break
            time.sleep(0.05)
        time.sleep(0.1)

    def test_original_export_records_history(self):
        """免转码快速路径必须写入导出历史（0.6.20 缺陷回归）。"""
        self.assertEqual(self.bridge.exportProcessed(
            [self.pids[0]], self.dest, "original", "original"), 1)
        self._wait_export_done()
        self.assertEqual(self.bridge.exportHistoryCount(), 1)
        rows = self.bridge.exportHistory(0, 10)
        self.assertEqual(rows[0]["name"], "a.jpg")
        self.assertEqual(rows[0]["fmt"], "original")
        self.assertEqual(rows[0]["destDir"], self.dest)

    def test_recode_export_records_history(self):
        """转码路径（jpg+短边）同样写入导出历史。"""
        self.assertEqual(self.bridge.exportProcessed(
            [self.pids[1]], self.dest, "jpg", "s800"), 1)
        self._wait_export_done()
        rows = self.bridge.exportHistory(0, 10)
        self.assertEqual(self.bridge.exportHistoryCount(), 1)
        self.assertEqual(rows[0]["fmt"], "jpg")
        self.assertEqual(rows[0]["res"], "s800")

    def test_history_order_and_fields(self):
        """多条记录按时间倒序，字段齐全。"""
        self.bridge.exportProcessed(self.pids, self.dest, "original", "original")
        self._wait_export_done()
        self.assertEqual(self.bridge.exportHistoryCount(), 2)
        rows = self.bridge.exportHistory(0, 10)
        self.assertEqual({r["name"] for r in rows}, {"a.jpg", "b.jpg"})
        for r in rows:
            self.assertIn("exportedAt", r)
            self.assertIn("photoId", r)


if __name__ == "__main__":
    unittest.main()
