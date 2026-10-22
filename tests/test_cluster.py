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
"""阶段2 聚类测试：事件时间聚类 + 人脸聚类（合成描述子，无需 AI 模型）。"""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from photo_manager.core.db import Database
from photo_manager.core.events import EventClusterer
from photo_manager.core.facecluster import FaceClusterer


class TestEvents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "lib.db").connect()
        c = self.db.conn
        c.executemany(
            "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size, file_mtime, taken_at)"
            " VALUES (?,?,?,?,?,?,?)",
            [
                ("a/1.jpg", "1.jpg", "a", ".jpg", 1, 1.0, "2024-01-01T10:00:00"),
                ("a/2.jpg", "2.jpg", "a", ".jpg", 1, 1.0, "2024-01-01T11:00:00"),
                ("a/3.jpg", "3.jpg", "a", ".jpg", 1, 1.0, "2024-01-01T21:00:00"),
                ("a/4.jpg", "4.jpg", "a", ".jpg", 1, 1.0, "2024-01-02T09:00:00"),
            ],
        )
        c.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_cluster_by_gap(self):
        stats = EventClusterer(self.db, gap_hours=4.0).run()
        self.assertEqual(stats["events"], 3)
        events = self.db.conn.execute("SELECT id, start_at, end_at, photo_count FROM events ORDER BY id").fetchall()
        self.assertEqual([e[3] for e in events], [2, 1, 1])  # 10:00/11:00 | 21:00 | 次日09:00
        self.assertEqual(events[0][1], "2024-01-01")
        self.assertEqual(events[2][1], "2024-01-02")


class TestFaceCluster(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "lib.db").connect()
        c = self.db.conn
        c.executemany(
            "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size, file_mtime)"
            " VALUES (?,?,?,?,?,?)",
            [(f"p/{i}.jpg", f"{i}.jpg", "p", ".jpg", 1, 1.0) for i in range(1, 13)],
        )
        rng = np.random.default_rng(7)
        base = rng.normal(size=(3, 128)).astype(np.float32)
        descs = []
        for b, n in zip(base, (5, 3, 4)):
            for _ in range(n):
                descs.append((b + rng.normal(scale=0.02, size=128)).astype(np.float32).tobytes())
        c.executemany(
            "INSERT INTO faces(photo_id, bbox, descriptor, score) VALUES (?,?,?,?)",
            [(i + 1, "[0,0,10,10]", d, 0.9) for i, d in enumerate(descs)],
        )
        c.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_cluster_three_persons(self):
        stats = FaceClusterer(self.db, threshold=0.85).run()
        self.assertEqual(stats["faces"], 12)
        self.assertEqual(stats["persons"], 3)
        counts = {r[0]: r[1] for r in self.db.conn.execute("SELECT id, face_count FROM persons")}
        self.assertEqual(sorted(counts.values()), [3, 4, 5])
        self.assertFalse(stats["scoped"])


if __name__ == "__main__":
    unittest.main()
