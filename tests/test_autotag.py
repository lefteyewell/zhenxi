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
"""自动标签规则测试：按路径关键词推断场景标签、幂等、自定义词表（0.5.26）。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from photo_manager.core.autotag import (
    SCENE_CLIP_TAGS,
    auto_tag_clip,
    auto_tag_library,
    merge_custom_words,
    parse_custom_tags,
    resolve_scene_vocab,
)
from photo_manager.core.db import Database


class TestAutoTag(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "t.db").connect()
        c = self.db.conn
        c.executemany(
            "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size, file_mtime)"
            " VALUES (?,?,?,?,?,?)",
            [
                ("D:/照片/2025-08-10_海边旅行/a1.jpg", "a1.jpg", "D:/照片/2025-08-10_海边旅行", ".jpg", 1, 1.0),
                ("D:/照片/2025-03-02_公司年会/a2.jpg", "a2.jpg", "D:/照片/2025-03-02_公司年会", ".jpg", 1, 1.0),
                ("D:/照片/写真集/a3.jpg", "a3.jpg", "D:/照片/写真集", ".jpg", 1, 1.0),
                ("D:/普通/a4.jpg", "a4.jpg", "D:/普通", ".jpg", 1, 1.0),
            ],
        )
        c.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _tags_of(self, name):
        return {r[0] for r in self.db.conn.execute(
            "SELECT t.tag FROM photo_tags t JOIN photos p ON p.id=t.photo_id"
            " WHERE p.file_name=?", (name,))}

    def test_scene_tags(self):
        # 自动场景标签统一写在「场景/」层级下（C10），与手打顶层标签区分
        auto_tag_library(self.db)
        self.assertIn("场景/旅行", self._tags_of("a1.jpg"), "海边旅行→场景/旅行")
        self.assertIn("场景/风景", self._tags_of("a1.jpg"), "海边→场景/风景")
        self.assertIn("场景/年会", self._tags_of("a2.jpg"), "公司年会→场景/年会")
        self.assertIn("场景/写真", self._tags_of("a3.jpg"), "写真集→场景/写真")
        self.assertEqual(self._tags_of("a4.jpg"), set(), "无关照片不误打")

    def test_idempotent(self):
        s1 = auto_tag_library(self.db)
        s2 = auto_tag_library(self.db)
        self.assertGreaterEqual(s1["added"], 1)
        self.assertEqual(s2["added"], 0, "重复执行不应新增标签")

    def test_clip_branch_safe(self):
        """CLIP 分支安全：无论模型是否就位，都不应崩、不误打标签；无图像向量时零样本标签为 0。

        本库尚未生成 photo_embeddings，因此 CLIP 零样本分支即使模型可用也应新增 0 个标签，
        标签完全由关键词兜底驱动（验证「先关键词、后 CLIP」的优先级与幂等）。
        """
        s = auto_tag_library(self.db)
        clip_stats = s.get("clip", {})
        self.assertIn("clip", s, "应返回 clip 分支统计")
        # 无向量时零样本标签必须为 0（不应误打）
        self.assertEqual(clip_stats.get("added", 0), 0,
                         "无图像向量时 CLIP 不应新增任何标签")
        # 关键词兜底不受影响（同样带「场景/」前缀）
        self.assertIn("场景/旅行", self._tags_of("a1.jpg"))
        # 无关照片仍不打标签
        self.assertEqual(self._tags_of("a4.jpg"), set())


class TestParseCustomTags(unittest.TestCase):
    """自定义场景词表解析（0.5.26/0.5.27）：自动分析链与工具中心共用同一段逻辑。"""

    def test_empty_returns_empty(self):
        self.assertEqual(parse_custom_tags(""), [])
        self.assertEqual(parse_custom_tags(None), [])
        self.assertEqual(parse_custom_tags("  ， \n ，"), [])

    def test_separators(self):
        self.assertEqual(parse_custom_tags("星空, 美食\n沙漠，夜市"),
                         ["星空", "美食", "沙漠", "夜市"])

    def test_minus_prefix_preserved(self):
        self.assertEqual(parse_custom_tags("星空, -宠物"), ["星空", "-宠物"])


class TestResolveSceneVocab(unittest.TestCase):
    """最终词表 = 内置 ∪ 自定义，「-词」排除内置（0.5.27 追加合并语义）。"""

    def test_empty_is_builtin(self):
        self.assertEqual(resolve_scene_vocab(""), list(SCENE_CLIP_TAGS))
        self.assertEqual(resolve_scene_vocab(None), list(SCENE_CLIP_TAGS))

    def test_custom_appended(self):
        v = resolve_scene_vocab("星空, 航拍")
        self.assertEqual(v[:len(SCENE_CLIP_TAGS)], list(SCENE_CLIP_TAGS))
        self.assertEqual(v[len(SCENE_CLIP_TAGS):], ["星空", "航拍"])

    def test_builtin_not_duplicated(self):
        v = resolve_scene_vocab("日落, 星空")
        self.assertEqual(v.count("日落"), 1)

    def test_minus_excludes_builtin(self):
        v = resolve_scene_vocab("-宠物")
        self.assertNotIn("宠物", v)
        self.assertIn("日落", v, "其它内置词不受影响")

    def test_exclusion_wins_over_add(self):
        # 排除优先于追加：「-宠物 宠物」结果不含宠物（同词冲突时保守处理）
        v = resolve_scene_vocab("-宠物, 宠物")
        self.assertNotIn("宠物", v)

    def test_excluding_everything_yields_empty(self):
        v = resolve_scene_vocab(",".join(f"-{t}" for t in SCENE_CLIP_TAGS))
        self.assertEqual(v, [], "全部排除=不打任何场景标签，而不是回退内置")


class TestMergeCustomWords(unittest.TestCase):
    """场景建议采纳 → 并入自定义词表（0.5.27）。"""

    def test_append_and_dedup(self):
        text, n = merge_custom_words("星空", ["星空", "航拍"])
        self.assertEqual(text, "星空, 航拍")
        self.assertEqual(n, 1)

    def test_unexclude(self):
        text, n = merge_custom_words("-宠物, 星空", ["宠物"])
        self.assertEqual(text, "星空, 宠物")
        self.assertEqual(n, 1, "推翻排除计为新增")

    def test_empty_base(self):
        text, n = merge_custom_words("", ["a", "b"])
        self.assertEqual((text, n), ("a, b", 2))


class TestAutoTagClipCustomTags(unittest.TestCase):
    """CLIP 零样本打标尊重自定义词表（0.5.26 修复：自动链曾固定用内置 29 词）。"""

    def setUp(self):
        from photo_manager.core.clip import MODEL_ID

        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "clip.db").connect()
        c = self.db.conn
        # 3 张照片 + 4 维假图像向量：p1↔星空、p2↔美食、p3↔两者皆非（model 必须用真实 MODEL_ID）
        self.vids = {}
        for i, (name, v) in enumerate([("p1.jpg", [1, 0, 0, 0]),
                                       ("p2.jpg", [0, 1, 0, 0]),
                                       ("p3.jpg", [0, 0, 1, 0])], 1):
            c.execute(
                "INSERT INTO photos(id, file_path, file_name, folder_path, ext, file_size,"
                " file_mtime, taken_at, sort_key, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (900 + i, f"x/{name}", name, "x", ".jpg", 1, 1.0,
                 "2025-01-01T00:00:00", "2025-01-01T00:00:00", "indexed"),
            )
            import numpy as np
            arr = np.array(v, dtype=np.float32)
            arr /= np.linalg.norm(arr)
            c.execute(
                "INSERT INTO photo_embeddings(photo_id, embedding, model, dim) VALUES (?,?,?,?)",
                (900 + i, arr.tobytes(), MODEL_ID, 4),
            )
            self.vids[name] = arr
        c.commit()

        # 假文本编码器：按词返回对应方向的单位向量
        text_map = {"星空": [1, 0, 0, 0], "美食": [0, 1, 0, 0]}
        import numpy as np

        def fake_encode_text(word):
            import numpy as np
            v = text_map.get(word, [0, 0, 0, 1])  # 未知词给正交方向，模拟"谁都不像"
            arr = np.array(v, dtype=np.float32)
            return arr / np.linalg.norm(arr)

        self.svc = SimpleNamespace(available=True, encode_text=fake_encode_text)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _tags(self, name):
        return {r[0] for r in self.db.conn.execute(
            "SELECT t.tag FROM photo_tags t JOIN photos p ON p.id=t.photo_id"
            " WHERE p.file_name=?", (name,))}

    def test_custom_tags_respected(self):
        stats = auto_tag_clip(self.db, svc=self.svc, tags=["星空", "美食"])
        self.assertTrue(stats["clip"])
        self.assertIn("场景/星空", self._tags("p1.jpg"))
        self.assertIn("场景/美食", self._tags("p2.jpg"))
        self.assertEqual(self._tags("p3.jpg"), set(), "两个候选都不匹配时不打标")
        # 内置词（如 风景/人像）不得越权出现——自定义词表整体替换内置词表
        for t in self._tags("p1.jpg") | self._tags("p2.jpg"):
            self.assertIn(t, {"场景/星空", "场景/美食"})

    def test_unmatched_word_tags_nothing(self):
        """自定义词与图像全不匹配：不崩、零写入。"""
        stats = auto_tag_clip(self.db, svc=self.svc, tags=["不存在的东西"])
        self.assertEqual(stats["added"], 0)

    def test_idempotent(self):
        auto_tag_clip(self.db, svc=self.svc, tags=["星空", "美食"])
        stats = auto_tag_clip(self.db, svc=self.svc, tags=["星空", "美食"])
        self.assertEqual(stats["added"], 0, "重复执行不应新增")


if __name__ == "__main__":
    unittest.main()