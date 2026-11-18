"""P1 回归：.livp（Live Photo 打包）扫描期解包入库。

用 pillow_heif 编码 HEIC、cv2 VideoWriter 生成 MOV 构造真实 .livp 样本，
覆盖：解包产物、两条记录入库、增量（源未变跳过 / 变更重析 / 产物丢失
重解包）、源消失标 missing、无视频成员、坏包容错。
"""
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import pillow_heif  # noqa: E402

pillow_heif.register_heif_opener()

from photo_manager.core.db import Database  # noqa: E402
from photo_manager.core.livp import (  # noqa: E402
    check_livp_missing,
    extract_livp,
    sync_livp,
)
from photo_manager.core.scanner import FileInfo, Scanner  # noqa: E402


def _make_livp(path: str, with_video: bool = True):
    """构造真实 .livp（zip：HEIC + MOV）。"""
    img = Image.new("RGB", (400, 300), (120, 40, 200))
    img.save(os.path.join(path + ".heic"), quality=80)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[:, :, 2] = 200
    mp4 = path + ".mp4"
    vw = cv2.VideoWriter(mp4, cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    vw.write(frame)
    vw.release()
    with zipfile.ZipFile(path, "w") as zf:
        zf.write(path + ".heic", "IMG_0001.HEIC")
        if with_video:
            zf.write(mp4, "IMG_0001.MOV")
    os.unlink(path + ".heic")
    os.unlink(mp4)


def _info(livp_path: str, mtime=None):
    st = os.stat(livp_path)
    return FileInfo(
        file_path=livp_path.replace("\\", "/"),
        file_name=os.path.basename(livp_path),
        folder_path=os.path.dirname(livp_path).replace("\\", "/"),
        ext=".livp",
        file_size=st.st_size if mtime is None else st.st_size,
        file_mtime=st.st_mtime if mtime is None else mtime,
    )


class LivpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="livp_")
        self.db = Database(os.path.join(self.tmp, "library.db")).connect()
        # 照片文件夹 + 数据目录分离（data 在 tmp 内部另一子目录）
        self.album = os.path.join(self.tmp, "album")
        self.data = os.path.join(self.tmp, "data")
        os.makedirs(self.album)
        os.makedirs(self.data)
        self.db_path = os.path.join(self.data, "library.db")
        self.db = Database(self.db_path).connect()

    def tearDown(self):
        self.db.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _livp(self, name="IMG_0001.livp", with_video=True):
        p = os.path.join(self.album, name)
        _make_livp(p, with_video=with_video)
        return p

    def test_extract_products(self):
        p = self._livp()
        res = extract_livp(p, self.db_path)
        self.assertIsNotNone(res)
        photo_path, video_path = res
        self.assertTrue(os.path.exists(photo_path))
        self.assertTrue(os.path.exists(video_path))
        with Image.open(photo_path) as im:
            self.assertEqual(im.size, (400, 300))
        cap = cv2.VideoCapture(video_path)
        self.assertTrue(cap.isOpened())
        cap.release()

    def test_sync_creates_two_pending_rows(self):
        p = self._livp()
        n = sync_livp(_info(p), self.db)
        self.assertEqual(n, 2)
        rows = self.db.conn.execute(
            "SELECT file_path, folder_path, status, media_type FROM photos"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        for fp, folder, status, media in rows:
            self.assertEqual(status, "pending")
            self.assertEqual(folder, self.album.replace("\\", "/"))
            self.assertIn(media, ("photo", "video"))
            self.assertFalse(fp.lower().endswith(".livp"))
        src = self.db.conn.execute(
            "SELECT photo_path, video_path FROM livp_sources"
        ).fetchone()
        self.assertEqual(src[0], rows[0][0] if rows[0][0].lower().endswith(".heic")
                         else rows[1][0])

    def test_sync_unchanged_skips(self):
        p = self._livp()
        info = _info(p)
        self.assertEqual(sync_livp(info, self.db), 2)
        self.assertEqual(sync_livp(info, self.db), 0)

    def test_sync_changed_reprocesses(self):
        p = self._livp()
        info = _info(p)
        sync_livp(info, self.db)
        # 人为把记录置为 indexed，模拟已分析；源变更后应回 pending
        self.db.conn.execute("UPDATE photos SET status='indexed', face_done=1")
        self.db.conn.commit()
        import time as _t
        info2 = _info(p, mtime=info.file_mtime + 10)
        n = sync_livp(info2, self.db)
        self.assertEqual(n, 2)
        for (status,) in self.db.conn.execute("SELECT status FROM photos"):
            self.assertEqual(status, "pending")

    def test_sync_recovers_lost_products(self):
        p = self._livp()
        info = _info(p)
        sync_livp(info, self.db)
        photo_path, video_path = self.db.conn.execute(
            "SELECT photo_path, video_path FROM livp_sources"
        ).fetchone()
        os.unlink(photo_path)
        os.unlink(video_path)
        # 源未变但产物丢失 → 重解包、置回 pending
        self.assertEqual(sync_livp(info, self.db), 2)
        self.assertTrue(os.path.exists(photo_path))

    def test_missing_marks_rows(self):
        p = self._livp()
        sync_livp(_info(p), self.db)
        os.unlink(p)
        n = check_livp_missing(self.db)
        self.assertEqual(n, 2)
        for (status,) in self.db.conn.execute("SELECT status FROM photos"):
            self.assertEqual(status, "missing")

    def test_livp_without_video(self):
        p = self._livp(with_video=False)
        self.assertEqual(sync_livp(_info(p), self.db), 1)
        media = [r[0] for r in self.db.conn.execute("SELECT media_type FROM photos")]
        self.assertEqual(media, ["photo"])

    def test_bad_zip_tolerated(self):
        p = os.path.join(self.album, "broken.livp")
        with open(p, "wb") as f:
            f.write(b"not a zip at all")
        self.assertEqual(sync_livp(_info(p), self.db), 0)
        self.assertEqual(
            self.db.conn.execute("SELECT count(*) FROM photos").fetchone()[0], 0)

    def test_scanner_routes_livp(self):
        p = self._livp()
        res = Scanner(self.db).scan([self.album])
        self.assertEqual(len(res.new_files), 0)  # .livp 不作为普通文件入库
        exts = [r[0] for r in self.db.conn.execute("SELECT ext FROM photos")]
        self.assertEqual(sorted(exts), [".heic", ".mov"])
        # 二次扫描：源未变，无新增变更
        res2 = Scanner(self.db).scan([self.album])
        self.assertEqual(len(res2.changed_files), 0)


if __name__ == "__main__":
    unittest.main()
