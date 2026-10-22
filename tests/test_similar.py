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
"""以图搜图（相似照片，CLIP 向量余弦）回归测试。

用合成的归一化向量验证 core.clip.find_similar：
- 相似度降序、排除自身、排除 missing/已归档；
- 查询照片无向量时安全返回空（不崩、不要求模型文件）。

对照实现：
- core/clip.py: find_similar(db, photo_id, topk)
- ui/library_bridge.py: findSimilar/similarCount/similarPhotos 后台槽
"""
import struct
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.clip import MODEL_ID, find_similar
from photo_manager.core.db import Database


def _add(db: Database, fname: str, **kw) -> int:
    cur = db.conn.execute(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
        " file_mtime, taken_at, sort_key, width, height, status, archived)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (kw.get("file_path", fname), fname, "/trip", "jpg", 1, 1.0,
         kw.get("taken_at", "2020-01-01T10:00:00"),
         kw.get("taken_at", "2020-01-01T10:00:00"),
         1000, 800, kw.get("status", "indexed"), kw.get("archived", 0)),
    )
    return cur.lastrowid


def _set_emb(db: Database, photo_id: int, vec) -> None:
    db.conn.execute(
        "INSERT OR REPLACE INTO photo_embeddings(photo_id, embedding, model, dim)"
        " VALUES (?,?,?,?)",
        (photo_id, struct.pack(f"<{len(vec)}f", *vec), MODEL_ID, len(vec)),
    )


def _norm(vals):
    n = sum(v * v for v in vals) ** 0.5
    return [v / n for v in vals]


class TestFindSimilar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "similar.db").connect()
        # 三张照片两两正交/同向，便于断言排序
        self.a = _add(self.db, "a.jpg", taken_at="2020-01-01T10:00:00")
        self.b = _add(self.db, "b.jpg", taken_at="2020-02-01T10:00:00")
        self.c = _add(self.db, "c.jpg", taken_at="2020-03-01T10:00:00")
        _set_emb(self.db, self.a, _norm([1.0, 0.0, 0.0]))
        _set_emb(self.db, self.b, _norm([1.0, 0.0, 0.0]))   # 与 a 同向 → 最相似
        _set_emb(self.db, self.c, _norm([0.0, 1.0, 0.0]))   # 与 a 正交 → 次之

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_order_and_exclusion(self):
        res = find_similar(self.db, self.a, topk=10)
        ids = [pid for pid, _ in res]
        self.assertNotIn(self.a, ids)          # 排除自身
        self.assertEqual(ids[0], self.b)       # 同向量排最前
        self.assertIn(self.c, ids)
        # 分数区间与排序
        scores = [s for _, s in res]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertGreater(scores[0], scores[-1])
        self.assertTrue(all(-1.001 <= s <= 1.001 for s in scores))

    def test_excludes_missing_and_archived(self):
        _set_emb(self.db, self.c, _norm([0.9, 0.1, 0.0]))  # 让 c 比 b 更相似
        self.db.conn.execute("UPDATE photos SET status='missing' WHERE id=?", (self.c,))
        self.db.conn.commit()
        ids = [pid for pid, _ in find_similar(self.db, self.a)]
        self.assertNotIn(self.c, ids)
        self.assertIn(self.b, ids)
        # 归档同理
        self.db.conn.execute("UPDATE photos SET status='indexed' WHERE id=?", (self.c,))
        self.db.conn.execute("UPDATE photos SET archived=1 WHERE id=?", (self.c,))
        self.db.conn.commit()
        ids2 = [pid for pid, _ in find_similar(self.db, self.a)]
        self.assertNotIn(self.c, ids2)
        self.assertIn(self.b, ids2)

    def test_query_without_embedding_returns_empty(self):
        d = _add(self.db, "d.jpg", taken_at="2020-04-01T10:00:00")
        self.assertEqual(find_similar(self.db, d), [])

    def test_no_embeddings_at_all_returns_empty(self):
        self.db.conn.execute("DELETE FROM photo_embeddings")
        self.db.conn.commit()
        self.assertEqual(find_similar(self.db, self.a), [])

    def test_topk_limit(self):
        res = find_similar(self.db, self.a, topk=1)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][0], self.b)

    def test_unnormalized_db_vectors_still_ranked(self):
        # 历史版本向量未归一化的兼容：模长 10 的向量方向相同，应仍排最前
        _set_emb(self.db, self.b, [10.0, 0.0, 0.0])
        res = find_similar(self.db, self.a)
        self.assertEqual(res[0][0], self.b)
        self.assertLessEqual(res[0][1], 1.001)  # 余弦不超 1


if __name__ == "__main__":
    unittest.main()
