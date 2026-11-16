# PhotoManager - 照片管理系统
# Copyright (C) 2026 蒙汗药
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 (the License), or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""首启按版本重置 RAW 分析状态的迁移回归测试。

守护的不变量：
1. 老库（无 meta.raw_reader_version）升级后，历史 RAW 的人脸 / OCR 结果
   与派生记录全部作废，且只作废一次；
2. 普通照片、视频、语义向量、其它类别的错误信息一条不动；
3. 43 种品牌 RAW 扩展名一视同仁；
4. 新库直接打标记，此后新导入并分析过的 RAW 不会被下次启动误伤。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from photo_manager.core.db import Database
from photo_manager.core.rawio import RAW_EXTS, RAW_READER_VERSION


class RawAnalysisMigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "lib.db")
        # 全新库：首次 connect 就会写入 raw_reader_version 标记
        self.db = Database(self.path).connect()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    # ---------- helpers ----------

    def _seed_photo(self, file_path, *, media_type="photo", error=None,
                    face_done=1, face_count=0, ocr_done=1):
        """造一张「已分析完」的照片及其派生记录（模拟升级前的库）。"""
        c = self.db.conn
        name = os.path.basename(file_path)
        ext = os.path.splitext(name)[1].lower()
        c.execute(
            "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
            " file_mtime, taken_at, sort_key, status, media_type)"
            " VALUES (?,?,?,?,?,?,?,?,'indexed',?)",
            (file_path, name, "/fake", ext, 1000, 100.0,
             "2025-03-02T10:00:00", "2025-03-02T10:00:00", media_type),
        )
        pid = c.execute(
            "SELECT id FROM photos WHERE file_path=?", (file_path,)).fetchone()[0]
        c.execute(
            "UPDATE photos SET face_done=?, face_count=?, ocr_done=?,"
            " ocr_text='stale text', has_text=1, error=? WHERE id=?",
            (face_done, face_count, ocr_done, error, pid),
        )
        c.execute(
            "INSERT INTO faces(photo_id, bbox, descriptor, score)"
            " VALUES (?, '[0,0,10,10]', X'00', 0.9)", (pid,))
        c.execute(
            "INSERT INTO ocr_texts(photo_id, text, conf)"
            " VALUES (?, 'stale text', 0.9)", (pid,))
        c.execute(
            "INSERT INTO ocr_fts(rowid, ocr_text) VALUES (?, 'stale text')", (pid,))
        c.commit()
        return pid

    def _reopen(self):
        self.db.close()
        self.db = Database(self.path).connect()

    def _simulate_upgrade(self):
        """删掉版本标记模拟 0.6.30 之前的老库，重新连接即触发迁移。"""
        self.db.conn.execute(
            "DELETE FROM meta WHERE key='raw_reader_version'")
        self.db.conn.commit()
        self._reopen()

    def _row(self, pid):
        return self.db.conn.execute(
            "SELECT face_done, face_count, ocr_done, ocr_text, has_text, error"
            " FROM photos WHERE id=?", (pid,)).fetchone()

    def _marker(self):
        row = self.db.conn.execute(
            "SELECT value FROM meta WHERE key='raw_reader_version'").fetchone()
        return row[0] if row else None

    # ---------- tests ----------

    def test_fresh_library_is_marked_immediately(self):
        self.assertEqual(self._marker(), str(RAW_READER_VERSION))
        # 新库导入并分析完的 RAW，下次启动不该被误伤
        pid = self._seed_photo("/fake/new.ARW")
        self._reopen()
        self.assertEqual(self._row(pid)[0], 1)
        self.assertEqual(
            self.db.conn.execute(
                "SELECT count(*) FROM faces WHERE photo_id=?", (pid,)).fetchone()[0], 1)

    def test_old_library_raw_state_invalidated_but_jpeg_untouched(self):
        raw = self._seed_photo("/fake/IMG_001.ARW", error="face: 无法读取图片")
        jpg = self._seed_photo("/fake/IMG_002.JPG", error="face: keep me")
        self._simulate_upgrade()

        self.assertEqual(self._row(raw), (0, 0, 0, "", 0, None))
        self.assertEqual(self._row(jpg), (1, 0, 1, "stale text", 1, "face: keep me"))
        self.assertEqual(self._marker(), str(RAW_READER_VERSION))
        c = self.db.conn
        for sql, arg in (
            ("SELECT count(*) FROM faces WHERE photo_id=?", raw),
            ("SELECT count(*) FROM ocr_texts WHERE photo_id=?", raw),
            ("SELECT count(*) FROM ocr_fts WHERE rowid=?", raw),
        ):
            self.assertEqual(c.execute(sql, (arg,)).fetchone()[0], 0, sql)
        self.assertEqual(
            c.execute("SELECT count(*) FROM faces WHERE photo_id=?", (jpg,)).fetchone()[0], 1)

    def test_second_connect_does_not_reset_reanalyzed_results(self):
        raw = self._seed_photo("/fake/IMG_001.NEF")
        self._simulate_upgrade()
        # 模拟用户重跑人脸检测后得到的新结果
        c = self.db.conn
        c.execute(
            "UPDATE photos SET face_done=1, face_count=2, ocr_done=1, ocr_text='new'"
            " WHERE id=?", (raw,))
        c.execute(
            "INSERT INTO faces(photo_id, bbox, descriptor, score)"
            " VALUES (?, '[1,2,3,4]', X'00', 0.8)", (raw,))
        c.commit()
        self._reopen()
        row = self._row(raw)
        self.assertEqual((row[0], row[1], row[2], row[3]), (1, 2, 1, "new"))
        self.assertEqual(
            self.db.conn.execute(
                "SELECT count(*) FROM faces WHERE photo_id=?", (raw,)).fetchone()[0], 1)

    def test_only_face_and_ocr_errors_are_cleared(self):
        face_err = self._seed_photo("/fake/a.ARW", error="face: decode failed")
        ocr_err = self._seed_photo("/fake/b.CR3", error="ocr: LoadImageError")
        other = self._seed_photo("/fake/c.DNG", error="decode: keep me")
        self._simulate_upgrade()
        self.assertIsNone(self._row(face_err)[5])
        self.assertIsNone(self._row(ocr_err)[5])
        self.assertEqual(self._row(other)[5], "decode: keep me")

    def test_video_with_raw_extension_is_untouched(self):
        vid = self._seed_photo("/fake/clip.ARW", media_type="video")
        self._simulate_upgrade()
        self.assertEqual(self._row(vid)[0], 1)
        self.assertEqual(
            self.db.conn.execute(
                "SELECT count(*) FROM faces WHERE photo_id=?", (vid,)).fetchone()[0], 1)

    def test_all_brand_raw_extensions_are_reset(self):
        pids = [self._seed_photo("/fake/x" + ext) for ext in sorted(RAW_EXTS)]
        jpg = self._seed_photo("/fake/control.JPG")
        self._simulate_upgrade()
        for pid in pids:
            self.assertEqual(self._row(pid)[0], 0, pid)
            self.assertEqual(self._row(pid)[2], 0, pid)
        self.assertEqual(self._row(jpg)[0], 1)
        self.assertEqual(len(pids), 43)

    def test_semantic_embeddings_are_preserved(self):
        raw = self._seed_photo("/fake/IMG_001.RAF")
        self.db.conn.execute(
            "INSERT INTO photo_embeddings(photo_id, embedding, model)"
            " VALUES (?, X'00', 'test')", (raw,))
        self.db.conn.commit()
        self._simulate_upgrade()
        self.assertEqual(
            self.db.conn.execute(
                "SELECT count(*) FROM photo_embeddings WHERE photo_id=?", (raw,)
            ).fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
