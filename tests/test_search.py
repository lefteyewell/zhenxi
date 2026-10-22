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
"""搜索回归测试：普通词搜标签 / dates 末日含当日 / text 语法 / 中文子串 / 联想。"""
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.db import Database
from photo_manager.core.search import PhotoSearch


def _mk(db: Database) -> None:
    c = db.conn
    c.executemany(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size, file_mtime,"
        " taken_at, sort_key, has_text, ocr_text, camera_model, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("p/a1.jpg", "a1.jpg", "旅行", ".jpg", 1, 1.0,
             "2025-06-29T20:00:00", "2025-06-29T20:00:00", 0, "", "Canon", "indexed"),
            ("p/a2.jpg", "a2.jpg", "旅行", ".jpg", 1, 1.0,
             "2025-06-30T09:30:00", "2025-06-30T09:30:00", 1, "横幅文字 北京欢迎你", "Canon", "indexed"),
            ("p/a3.jpg", "a3.jpg", "家", ".jpg", 1, 1.0,
             "2025-06-30T23:00:00", "2025-06-30T23:00:00", 0, "", "Sony", "indexed"),
            ("p/a4.jpg", "a4.jpg", "公司", ".jpg", 1, 1.0,
             "2025-07-01T08:00:00", "2025-07-01T08:00:00", 0, "", "Nikon", "indexed"),
        ],
    )
    c.executemany(
        "INSERT INTO photo_tags(photo_id, tag) VALUES (?,?)",
        [(1, "旅行"), (1, "风景"), (2, "风景"), (3, "家庭")],
    )
    c.commit()


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "s.db").connect()
        _mk(self.db)
        self.s = PhotoSearch(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_plain_keyword_searches_tags(self):
        hits = self.s.query("旅行")
        names = [h["file_name"] for h in hits]
        self.assertIn("a1.jpg", names, "普通词应命中标签（旅行）")

    def test_dates_includes_last_day(self):
        hits = self.s.query("dates:2025-06-30..2025-06-30")
        names = [h["file_name"] for h in hits]
        self.assertIn("a2.jpg", names, "末日(6-30)整天都应包含，含当日 23:00")
        self.assertIn("a3.jpg", names, "6-30 23:00 属于末日，不应被排除")
        self.assertNotIn("a4.jpg", names)
        self.assertNotIn("a1.jpg", names)

    def test_text_syntax(self):
        self.assertEqual(len(self.s.query("text:")), 1, "text: 只返回含文字照片")
        self.assertEqual(len(self.s.query("text:北京")), 1)
        self.assertEqual(len(self.s.query("text:不存在")), 0)

    def test_chinese_substring(self):
        self.assertEqual(len(self.s.query("北京欢迎")), 1, "中文子串应命中 OCR 文本")
        self.assertEqual(len(self.s.query("横幅")), 1, "中文子串匹配")

    def test_tag_negation(self):
        hits = self.s.query("-tag:风景")
        names = [h["file_name"] for h in hits]
        self.assertNotIn("a1.jpg", names)
        self.assertIn("a3.jpg", names)

    def test_suggest(self):
        out = self.s.suggest("a")
        self.assertGreaterEqual(len(out), 1)

    def test_clip_search_empty_without_embeddings(self):
        """语义搜索 clip: 在库无图像向量时安全返回空（不崩、不误匹配）。

        测试库未执行 clip-index，photo_embeddings 为空，因此无论模型是否就位都应返回空。
        """
        hits = self.s.query("clip:海边日落的照片")
        self.assertEqual(hits, [], "无向量时 clip: 应返回空结果而非抛错")

    def test_gps_place_name_search(self):
        """gps:地名 → 逆地理编码解析为区域，命中区域内照片、排除区域外照片。"""
        c = self.db.conn
        c.execute(
            "INSERT INTO photos(file_path,file_name,folder_path,ext,file_size,file_mtime,"
            "taken_at,sort_key,status,gps_lat,gps_lon) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("p/bj.jpg", "bj.jpg", "北京", ".jpg", 1, 1.0,
             "2025-01-01T10:00:00", "2025-01-01T10:00:00", "indexed", 39.90, 116.40),
        )
        c.execute(
            "INSERT INTO photos(file_path,file_name,folder_path,ext,file_size,file_mtime,"
            "taken_at,sort_key,status,gps_lat,gps_lon) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("p/ny.jpg", "ny.jpg", "纽约", ".jpg", 1, 1.0,
             "2025-01-02T10:00:00", "2025-01-02T10:00:00", "indexed", 40.71, -74.0),
        )
        c.commit()
        hits = self.s.query("gps:北京")
        names = [h["file_name"] for h in hits]
        self.assertIn("bj.jpg", names, "北京坐标照片应被 gps:北京 命中")
        self.assertNotIn("ny.jpg", names, "纽约坐标照片不应被 gps:北京 命中")
        # 未知地名安全返回空
        self.assertEqual(self.s.query("gps:zzz不存在地名"), [])

    def test_camera_negation_with_null_meta(self):
        """回归：-camera:x 的排除搜索必须命中「无相机元数据」的照片。

        camera_make/model/lens 三列可空（无 EXIF 相机信息），旧代码
        NOT(camera_make LIKE ? OR ...) 在 NULL 列上三值逻辑为 NULL，
        导致 -camera:Canon 把所有照片全部排除、恒返回空。
        """
        c = self.db.conn
        c.execute(
            "INSERT INTO photos(file_path,file_name,folder_path,ext,file_size,file_mtime,"
            "taken_at,sort_key,status) VALUES (?,?,?,?,?,?,?,?,?)",
            ("p/noexif.jpg", "noexif.jpg", "家", ".jpg", 1, 1.0,
             "2025-06-30T12:00:00", "2025-06-30T12:00:00", "indexed"),
        )
        c.commit()
        neg = [h["file_name"] for h in self.s.query("-camera:Canon")]
        self.assertIn("noexif.jpg", neg, "无相机元数据的照片不是 Canon，应被 -camera:Canon 命中")
        self.assertIn("a3.jpg", neg)
        self.assertIn("a4.jpg", neg)
        self.assertNotIn("a1.jpg", neg)
        self.assertNotIn("a2.jpg", neg)
        # 正向搜索不受影响（结果按 sort_key DESC 排序，用无序比较）
        pos = [h["file_name"] for h in self.s.query("camera:Canon")]
        self.assertCountEqual(pos, ["a1.jpg", "a2.jpg"])

    def test_plain_query_semantic_fallback_no_model(self):
        """纯文本零命中时回退语义搜索：无模型/无向量时安全返回空（0.5.23）。"""
        res = self.s.query("室内不存在的词xyz")
        self.assertEqual(res, [])
        # 带语法前缀的查询不回退，行为不变
        res2 = self.s.query("tag:不存在的标签xyz")
        self.assertEqual(res2, [])

    def test_traditional_simplified_interchange(self):
        """繁简互通（0.5.25）：任一字形查询都能命中简体入库的标签/OCR/文件名。"""
        # 标签以简体「风景」入库，繁体「風景」查询应命中 a1/a2
        trad = [h["file_name"] for h in self.s.query("風景")]
        self.assertCountEqual(trad, ["a1.jpg", "a2.jpg"])
        # OCR 文本以简体「横幅」入库，繁体「橫幅」查询应命中 a2
        t = [h["file_name"] for h in self.s.query("text:橫幅")]
        self.assertEqual(t, ["a2.jpg"])
        # 纯文本繁体命中（文件名/OCR/标签任一路径）
        self.assertTrue(self.s.query("橫幅"))

    def test_clip_search_relative_threshold(self):
        """语义检索只保留 best-0.05 区间内照片，数量上限 50（0.5.24 修复回退带出大量无关）。"""
        import numpy as np
        from types import SimpleNamespace
        from unittest.mock import patch
        from photo_manager.core import clip as clip_mod
        from photo_manager.core.search import _clip_search_ids

        qv = np.array([1.0, 0, 0, 0], dtype=np.float32)
        fake = SimpleNamespace(available=True, encode_text=lambda _q: qv)
        c = self.db.conn
        # 与查询向量的余弦相似度：1.00 / 0.99 / 0.707 / 0
        vecs = {
            "v1.jpg": [1.0, 0.0, 0.0, 0.0],
            "v2.jpg": [0.99, 0.141, 0.0, 0.0],
            "v3.jpg": [0.707, 0.707, 0.0, 0.0],
            "v4.jpg": [0.0, 1.0, 0.0, 0.0],
        }
        for i, (name, v) in enumerate(vecs.items(), 1):
            c.execute(
                "INSERT INTO photos(id, file_path, file_name, folder_path, ext, file_size,"
                " file_mtime, taken_at, sort_key, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (100 + i, f"p/{name}", name, "v", ".jpg", 1, 1.0,
                 "2025-01-01T00:00:00", "2025-01-01T00:00:00", "indexed"),
            )
            arr = np.array(v, dtype=np.float32)
            arr /= np.linalg.norm(arr)
            c.execute(
                "INSERT INTO photo_embeddings(photo_id, embedding, model, dim) VALUES (?,?,?,?)",
                (100 + i, arr.tobytes(), clip_mod.MODEL_ID, 4),
            )
        c.commit()
        with patch.object(clip_mod, "get_service", return_value=fake):
            ids = _clip_search_ids(self.db, "任意")
            # v3(0.707)、v4(0) 在 best(1.0)-0.05 区间外，应被过滤
            self.assertEqual(ids, [101, 102])
            # 经 query() 的回退路径同样只出 2 张
            hits = self.s.query("完全不匹配的词")
            self.assertEqual([h["id"] for h in hits], [101, 102])


if __name__ == "__main__":
    unittest.main()

class TestSynonymExpansion(unittest.TestCase):
    """近义扩展（0.5.27）：纯文本与 tag: 自动展开组内近义词；
    引号=精确不扩展；-排除 不扩展；text: OCR 字段不扩展。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "syn.db").connect()
        c = self.db.conn
        c.executemany(
            "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size, file_mtime,"
            " taken_at, sort_key, has_text, ocr_text, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("p/p1.jpg", "p1.jpg", "p", ".jpg", 1, 1.0, "2025-01-01T00:00:00",
                 "2025-01-01T00:00:00", 0, "", "indexed"),
                ("p/wanxia.jpg", "晚霞.jpg", "p", ".jpg", 1, 1.0,
                 "2025-01-01T00:00:00", "2025-01-01T00:00:00", 0, "", "indexed"),
                ("p/p3.jpg", "p3.jpg", "p", ".jpg", 1, 1.0, "2025-01-01T00:00:00",
                 "2025-01-01T00:00:00", 1, "海边晚霞真美", "indexed"),
                ("p/p4.jpg", "p4.jpg", "p", ".jpg", 1, 1.0, "2025-01-01T00:00:00",
                 "2025-01-01T00:00:00", 0, "", "indexed"),
            ],
        )
        c.executemany("INSERT INTO photo_tags(photo_id, tag) VALUES (?,?)",
                      [(1, "场景/日落"), (4, "场景/美食")])
        c.commit()
        self.s = PhotoSearch(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _names(self, q):
        return sorted(h["file_name"] for h in self.s.query(q))

    def test_plain_expands_synonyms(self):
        self.assertEqual(self._names("晚霞"),
                         ["p1.jpg", "p3.jpg", "晚霞.jpg"],
                         "晚霞 应展开出 日落/黄昏/夕阳 命中 场景/日落 标签照片")

    def test_tag_prefix_expands(self):
        self.assertIn("p1.jpg", self._names("tag:晚霞"))
        self.assertIn("p1.jpg", self._names("tag:黄昏"), "组内任一词都可反向命中")

    def test_quoted_exact_no_expansion(self):
        self.assertEqual(self._names('"晚霞"'), ["p3.jpg", "晚霞.jpg"],
                         "引号=精确匹配，不展开到 日落 标签")

    def test_negation_no_expansion(self):
        self.assertIn("p1.jpg", self._names("-tag:晚霞"),
                      "排除条件不扩展近义词，日落标签照片不应被误排")

    def test_text_field_not_expanded(self):
        self.assertEqual(self._names("text:晚霞"), ["p3.jpg"],
                         "text: 走 OCR 字面匹配，不做近义扩展")

    def test_expansion_cap(self):
        from photo_manager.core.search import SYN_MAX_TERMS, _expand_synonyms
        for w, terms in (("晚霞", _expand_synonyms("晚霞")),
                         ("无组的词", _expand_synonyms("无组的词"))):
            self.assertLessEqual(len(terms), SYN_MAX_TERMS)
        self.assertEqual(_expand_synonyms("无组的词"), ["无组的词"])
