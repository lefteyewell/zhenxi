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
"""半自动场景建议测试（0.5.27）：领头聚类 + 未覆盖簇命名 + 降级安全。

CLIP 真模型不参与：注入 4 维假向量（与 test_search 相对阈值测试同一手法）。
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from photo_manager.core import scene_suggest
from photo_manager.core.clip import MODEL_ID
from photo_manager.core.db import Database
from photo_manager.core.scene_suggest import leader_cluster, suggest_scenes


def _unit(v):
    arr = np.array(v, dtype=np.float32)
    return arr / np.linalg.norm(arr)


class TestLeaderCluster(unittest.TestCase):
    def test_groups_and_deterministic(self):
        mat = np.stack([_unit([1, 0, 0, 0]), _unit([0.99, 0.1, 0, 0]),
                        _unit([0, 1, 0, 0]), _unit([0, 0.99, 0.1, 0]),
                        _unit([0, 0, 1, 0])])
        a = leader_cluster(mat, radius=0.8)
        b = leader_cluster(mat, radius=0.8)
        self.assertEqual(a, b, "同输入必须同输出")
        self.assertEqual(sorted(len(c) for c in a), [1, 2, 2])
        # 第 1、2 行同簇；第 5 行独簇
        flat = {i: ci for ci, c in enumerate(a) for i in c}
        self.assertEqual(flat[0], flat[1])
        self.assertNotEqual(flat[0], flat[4])

    def test_max_leaders_cap(self):
        basis = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        mat = np.stack([_unit(basis[i % 4]) for i in range(20)])
        clusters = leader_cluster(mat, radius=0.8, max_leaders=2)
        self.assertLessEqual(len(clusters), 2 + 1, "超限后不再新建簇")


class TestSuggestScenes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "sug.db").connect()
        c = self.db.conn
        # 6 张"星空"方向（未被词表覆盖）+ 5 张"风景"方向（被词表覆盖）+ 3 张其它方向（簇过小）
        plan = ([("st", [1, 0, 0, 0], 6), ("fv", [0, 1, 0, 0], 5),
                 ("sm", [0, 0, 1, 0], 3)])
        pid = 0
        for tag, base, n in plan:
            for k in range(n):
                pid += 1
                jitter = 0.02 * (k % 3)
                v = list(base)
                v[k % 4] += jitter
                c.execute(
                    "INSERT INTO photos(id, file_path, file_name, folder_path, ext, file_size,"
                    " file_mtime, taken_at, sort_key, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (pid, f"p/{pid}.jpg", f"{pid}.jpg", "p", ".jpg", 1, 1.0,
                     "2025-01-01T00:00:00", "2025-01-01T00:00:00", "indexed"),
                )
                c.execute(
                    "INSERT INTO photo_embeddings(photo_id, embedding, model, dim)"
                    " VALUES (?,?,?,?)",
                    (pid, _unit(v).tobytes(), MODEL_ID, 4),
                )
        c.commit()

        # 假文本编码器：词表词"风景"与候选池"星空"都有明确方向；未知词给正交方向
        text_map = {"风景": [0, 1, 0, 0], "星空": [1, 0, 0, 0]}

        def fake_encode_text(word):
            arr = np.array(text_map.get(word, [0, 0, 0, 1]), dtype=np.float32)
            return arr / np.linalg.norm(arr)

        self.svc = SimpleNamespace(available=True, encode_text=fake_encode_text)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_suggests_uncovered_cluster(self):
        r = suggest_scenes(self.db, svc=self.svc, vocab=["风景"])
        self.assertTrue(r["ok"])
        self.assertEqual(r["scanned"], 14)
        self.assertEqual(r["uncovered"], 9, "6 星空 + 3 小簇 都未覆盖")
        words = [s["word"] for s in r["suggestions"]]
        self.assertIn("星空", words)
        st = next(s for s in r["suggestions"] if s["word"] == "星空")
        self.assertEqual(st["count"], 6, "3 张的小簇低于 MIN_CLUSTER 不产生建议")
        self.assertGreater(len(st["examples"]), 0)

    def test_covered_library_no_suggestion(self):
        # 全库都被词表覆盖 → 零建议（只保留 5 张"风景"方向的向量）
        c = self.db.conn
        c.execute("DELETE FROM photo_embeddings WHERE photo_id <= 6 OR photo_id > 11")
        c.commit()
        r = suggest_scenes(self.db, svc=self.svc, vocab=["风景"])
        self.assertTrue(r["ok"])
        self.assertEqual(r["suggestions"], [])

    def test_no_embeddings(self):
        self.db.conn.execute("DELETE FROM photo_embeddings")
        self.db.conn.commit()
        r = suggest_scenes(self.db, svc=self.svc, vocab=["风景"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "no_embeddings")

    def test_model_missing(self):
        r = suggest_scenes(self.db,
                           svc=SimpleNamespace(available=False), vocab=["风景"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "model_missing")

    def test_pool_word_near_vocab_filtered(self):
        # 若候选池中最匹配的词与现有词近重复（文本相似度过高），应跳过换下一个词
        from photo_manager.core.scene_suggest import SUGGEST_POOL, NEAR_DUP_SIM
        self.assertIn("星空", SUGGEST_POOL)
        self.assertLess(NEAR_DUP_SIM, 1.0)


if __name__ == "__main__":
    unittest.main()
