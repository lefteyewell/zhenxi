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
"""SQLite 数据库层：schema、连接、FTS5 全文索引同步。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_VERSION = 1

# 人脸框坐标格式版本：仅当 bbox 的存储口径变化、历史框无法换算时 +1。
# 1 = 0.6.31：faces.bbox 改为 6 元素（自带检测图尺寸），修复相机 RAW 的
# 人脸框 / 头像裁剪整体错位；meta.face_bbox_version 记录已迁移版本。
FACE_BBOX_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_roots (
    path         TEXT PRIMARY KEY,
    last_scan_at TEXT
);

CREATE TABLE IF NOT EXISTS photos (
    id            INTEGER PRIMARY KEY,
    file_path     TEXT NOT NULL UNIQUE,
    file_name     TEXT NOT NULL,
    folder_path   TEXT NOT NULL,
    ext           TEXT NOT NULL,
    file_size     INTEGER NOT NULL,
    file_mtime    REAL NOT NULL,
    content_hash  TEXT,
    taken_at      TEXT,
    sort_key      TEXT NOT NULL DEFAULT '',
    camera_make   TEXT,
    camera_model  TEXT,
    lens_model    TEXT,
    exposure      TEXT,
    f_number      REAL,
    iso           INTEGER,
    focal_length  REAL,
    gps_lat       REAL,
    gps_lon       REAL,
    gps_alt       REAL,
    width         INTEGER,
    height        INTEGER,
    thumbnail_path TEXT,
    thumb_width   INTEGER,
    thumb_height  INTEGER,
    face_count    INTEGER NOT NULL DEFAULT 0,
    has_text      INTEGER NOT NULL DEFAULT 0,
    ocr_text      TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
    error         TEXT,
    indexed_at    TEXT,
    rating        INTEGER NOT NULL DEFAULT 0,
    flag          TEXT NOT NULL DEFAULT '',
    archived      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_photos_taken_at ON photos(taken_at);
CREATE INDEX IF NOT EXISTS idx_photos_folder    ON photos(folder_path);
CREATE INDEX IF NOT EXISTS idx_photos_status    ON photos(status);
CREATE INDEX IF NOT EXISTS idx_photos_taken_expr ON photos(COALESCE(taken_at, ''));
CREATE INDEX IF NOT EXISTS idx_photos_face_count ON photos(face_count);

CREATE TABLE IF NOT EXISTS faces (
    id          INTEGER PRIMARY KEY,
    photo_id    INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    bbox        TEXT NOT NULL,
    descriptor  BLOB NOT NULL,
    score       REAL,
    cluster_id  INTEGER,
    person_id   INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_faces_photo ON faces(photo_id);
CREATE INDEX IF NOT EXISTS idx_faces_cluster ON faces(cluster_id);
CREATE INDEX IF NOT EXISTS idx_faces_person ON faces(person_id);

CREATE TABLE IF NOT EXISTS ocr_texts (
    id         INTEGER PRIMARY KEY,
    photo_id   INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    text       TEXT NOT NULL,
    conf       REAL,
    bbox       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ocr_photo ON ocr_texts(photo_id);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    start_at    TEXT,
    end_at      TEXT,
    title       TEXT,
    center_lat  REAL,
    center_lon  REAL,
    photo_count INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS event_photos (
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, photo_id)
);

CREATE TABLE IF NOT EXISTS persons (
    id          INTEGER PRIMARY KEY,
    name        TEXT,
    face_count  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_persons_name ON persons(name);

CREATE TABLE IF NOT EXISTS photo_tags (
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    tag      TEXT NOT NULL,
    PRIMARY KEY (photo_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON photo_tags(tag);

CREATE VIRTUAL TABLE IF NOT EXISTS photos_fts USING fts5(
    file_name,
    folder_path,
    camera_make,
    camera_model,
    lens_model,
    ocr_text,
    content='photos',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

-- OCR 文本专用索引：trigram 子串匹配（中文/任意长度子串 ≥3 字符）
CREATE VIRTUAL TABLE IF NOT EXISTS ocr_fts USING fts5(
    ocr_text,
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS photos_ai AFTER INSERT ON photos BEGIN
    INSERT INTO photos_fts(rowid, file_name, folder_path, camera_make, camera_model, lens_model, ocr_text)
    VALUES (new.id, new.file_name, new.folder_path, new.camera_make, new.camera_model, new.lens_model, new.ocr_text);
END;

CREATE TRIGGER IF NOT EXISTS photos_ad AFTER DELETE ON photos BEGIN
    INSERT INTO photos_fts(photos_fts, rowid, file_name, folder_path, camera_make, camera_model, lens_model, ocr_text)
    VALUES ('delete', old.id, old.file_name, old.folder_path, old.camera_make, old.camera_model, old.lens_model, old.ocr_text);
END;

CREATE TRIGGER IF NOT EXISTS photos_au AFTER UPDATE ON photos BEGIN
    INSERT INTO photos_fts(photos_fts, rowid, file_name, folder_path, camera_make, camera_model, lens_model, ocr_text)
    VALUES ('delete', old.id, old.file_name, old.folder_path, old.camera_make, old.camera_model, old.lens_model, old.ocr_text);
    INSERT INTO photos_fts(rowid, file_name, folder_path, camera_make, camera_model, lens_model, ocr_text)
    VALUES (new.id, new.file_name, new.folder_path, new.camera_make, new.camera_model, new.lens_model, new.ocr_text);
END;

-- CLIP 语义向量：每张照片一条 512 维 float32（2048 字节）
-- model 字段用于区分不同模型产出的向量，换模型时不会误用旧向量
CREATE TABLE IF NOT EXISTS photo_embeddings (
    photo_id   INTEGER PRIMARY KEY REFERENCES photos(id) ON DELETE CASCADE,
    embedding  BLOB NOT NULL,
    model      TEXT NOT NULL DEFAULT 'cn-clip-vit-b-16',
    dim        INTEGER NOT NULL DEFAULT 512,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_emb_model ON photo_embeddings(model);

-- 视频关键帧（0.5.51）：视频入库时按时长均匀抽 N 帧存盘（相对 data 目录），
-- 供 CLIP 编码进语义检索（多帧平均向量写入 photo_embeddings）与信息面板帧带展示
CREATE TABLE IF NOT EXISTS video_frames (
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    idx      INTEGER NOT NULL,
    path     TEXT NOT NULL,
    PRIMARY KEY (photo_id, idx)
);

-- 虚拟相册：用户自建的分组（只存引用，不移动/复制任何照片文件）
CREATE TABLE IF NOT EXISTS albums (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS album_photos (
    album_id INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (album_id, photo_id)
);
CREATE INDEX IF NOT EXISTS idx_album_photos_photo ON album_photos(photo_id);

-- 复制入库映射：源路径 → 库内路径（源 mtime/size 未变则跳过重复导入）
CREATE TABLE IF NOT EXISTS library_imports (
    src_path  TEXT PRIMARY KEY,
    dest_path TEXT NOT NULL,
    src_mtime REAL,
    src_size  INTEGER
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> "Database":
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("PRAGMA cache_size=-65536")  # 64MB
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        return self

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
            (str(DB_VERSION),),
        )
        self.conn.commit()

    def _migrate(self) -> None:
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(photos)")}
        for name, ddl in {
            "face_done": "ALTER TABLE photos ADD COLUMN face_done INTEGER NOT NULL DEFAULT 0",
            "ocr_done": "ALTER TABLE photos ADD COLUMN ocr_done INTEGER NOT NULL DEFAULT 0",
            "perceptual_hash": "ALTER TABLE photos ADD COLUMN perceptual_hash TEXT",
            "sort_key": "ALTER TABLE photos ADD COLUMN sort_key TEXT NOT NULL DEFAULT ''",
            "rating": "ALTER TABLE photos ADD COLUMN rating INTEGER NOT NULL DEFAULT 0",
            "flag": "ALTER TABLE photos ADD COLUMN flag TEXT NOT NULL DEFAULT ''",
            "archived": "ALTER TABLE photos ADD COLUMN archived INTEGER NOT NULL DEFAULT 0",
            "color_label": "ALTER TABLE photos ADD COLUMN color_label TEXT",
            "stack_id": "ALTER TABLE photos ADD COLUMN stack_id INTEGER",
            # 0.5.44：视频管理 V1。media_type 区分 photo/video（老数据默认 photo）；
            # duration=视频时长(秒)。视频行走编目级：有缩略图+时长，但不做人脸/OCR/语义。
            "media_type": "ALTER TABLE photos ADD COLUMN media_type TEXT NOT NULL DEFAULT 'photo'",
            "duration": "ALTER TABLE photos ADD COLUMN duration REAL",
            "video_codec": "ALTER TABLE photos ADD COLUMN video_codec TEXT",
            # 0.5.64：损坏文件标记。1=全图数据无法解码（查看时经 make_preview
            # 兜底路径或深度解码检查发现）；0=正常/未检测。文件替换重新入库时重置。
            "decode_error": "ALTER TABLE photos ADD COLUMN decode_error INTEGER NOT NULL DEFAULT 0",
        }.items():
            if name not in cols:
                self.conn.execute(ddl)
        # 0.5.37：人脸模糊指数（Laplacian 方差归一化 0-100，越大越模糊）与隐藏标记。
        # hidden=1 仅在人物列表/人脸搜索/信息面板中隐藏，照片与检测数据不动。
        fcols = {r[1] for r in self.conn.execute("PRAGMA table_info(faces)")}
        if "blur" not in fcols:
            self.conn.execute("ALTER TABLE faces ADD COLUMN blur REAL")
        if "hidden" not in fcols:
            self.conn.execute(
                "ALTER TABLE faces ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0")
        # 0.5.39：导出历史（"已导出"导航页数据源；只记录，不参与任何删除）
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS export_records ("
            " id INTEGER PRIMARY KEY,"
            " photo_id INTEGER,"
            " file_name TEXT NOT NULL,"
            " dest_dir TEXT NOT NULL,"
            " fmt TEXT NOT NULL DEFAULT 'original',"
            " res TEXT NOT NULL DEFAULT 'original',"
            " exported_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_export_records_at"
            " ON export_records(exported_at)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS stacks ("
            " id INTEGER PRIMARY KEY,"
            " representative_photo_id INTEGER NOT NULL REFERENCES photos(id))"
        )
        self.conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_persons_name ON persons(name)"
        )
        if "sort_key" not in cols:
            self.conn.execute(
                "UPDATE photos SET sort_key = COALESCE(taken_at, '')"
                " WHERE sort_key = '' AND taken_at IS NOT NULL"
            )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photos_sort_key ON photos(sort_key)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photos_fc_sort ON photos(face_count, sort_key)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photos_rating ON photos(rating)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photos_flag ON photos(flag)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photos_archived ON photos(archived)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photos_stack_id ON photos(stack_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_person ON faces(person_id)"
        )
        # 0.6.14：重复页每次进入都 GROUP BY perceptual_hash（2.4 万行全表
        # 聚合），加索引走索引扫描
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photos_phash ON photos(perceptual_hash)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS analysis_state ("
            " stage TEXT PRIMARY KEY,"
            " finished_at TEXT,"
            " total_at_time INTEGER NOT NULL DEFAULT 0)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS move_out_records ("
            " id INTEGER PRIMARY KEY,"
            " dest_dir TEXT NOT NULL,"
            " file_name TEXT NOT NULL,"
            " moved_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_move_out_dir ON move_out_records(dest_dir)"
        )
        # ocr_fts 是独立 FTS 表（ocr.py 手动维护），删除照片时不会自动清理。
        # 残留的孤儿索引很危险：SQLite 会复用已删除的 rowid，新照片会"继承"
        # 旧照片的 OCR 文字，导致按文字搜出错误结果。用触发器在删照片时同步清理。
        self.conn.execute(
            "CREATE TRIGGER IF NOT EXISTS photos_ad_ocr_fts AFTER DELETE ON photos BEGIN"
            " DELETE FROM ocr_fts WHERE rowid = old.id;"
            " END"
        )
        # 0.6.20：疑似重复人物候选对（阶段一 Top-N 代表脸余弦扫描产物）。
        # a/b 为 person_id，b 固定为照片数较多的一方（合并方向）；ignored
        # 用户"忽略此对"后跨扫描持久。重聚类产生的死 id 读取时 INNER JOIN
        # persons 自然过滤，无需清理钩子。
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS person_dup_candidates ("
            " a INTEGER NOT NULL,"
            " b INTEGER NOT NULL,"
            " sim REAL NOT NULL,"
            " ignored INTEGER NOT NULL DEFAULT 0,"
            " scanned_at TEXT NOT NULL DEFAULT (datetime('now')),"
            " PRIMARY KEY (a, b))"
        )
        self._migrate_raw_analysis_state()
        self._migrate_face_bbox_state()
        self._migrate_container_raw_reindex()

    def _migrate_face_bbox_state(self) -> None:
        """0.6.31：一次性作废历史相机 RAW 的人脸框（人脸检测重跑一次）。

        0.6.30 让 RAW 首次检出人脸，但 bbox 写在「内嵌 JPEG 预览 /
        half_size 后处理图」的坐标系，界面却按 photos.width/height
        （LibRaw 传感器真实尺寸，0.6.30 起才正确记录）归一化，竖拍再叠加
        EXIF 宽高互换 → 框与头像裁剪整体错位。这批旧框在不重新解码原图的
        前提下无法反算，因此重置 face_done 让增量检测重跑并写入自带尺寸
        基准的新 bbox。

        刻意只动 RAW 且 media_type='photo' 的**人脸**：普通照片、OCR 结果
        （0.6.30 的文字识别结果有效）、语义向量、status、宽高、其它错误
        一律不动，避免整库重扫。meta.face_bbox_version 保证每个库只执行一次。

        删旧 faces 行前把「照片 → 人物名」备份进 face_name_backup：聚类是按
        脸 id 继承名字的，只在这批 RAW 上出现过的人物名会随旧行一起消失，
        由 FacePipeline 重跑检测时还原（见 faces._restore_face_name）。
        """
        from photo_manager.core.rawio import is_raw  # noqa: PLC0415

        row = self.conn.execute(
            "SELECT value FROM meta WHERE key='face_bbox_version'").fetchone()
        try:
            seen = int(row[0]) if row else 0
        except (TypeError, ValueError):
            seen = 0
        if seen >= FACE_BBOX_VERSION:
            return

        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS face_name_backup ("
            " photo_id INTEGER PRIMARY KEY, person_name TEXT NOT NULL)")
        rows = self.conn.execute(
            "SELECT id, file_path FROM photos WHERE media_type='photo'").fetchall()
        ids = [pid for pid, path in rows if is_raw(path)]
        for start in range(0, len(ids), 400):
            chunk = ids[start:start + 400]
            q = ",".join("?" * len(chunk))
            self.conn.execute(
                "INSERT OR REPLACE INTO face_name_backup(photo_id, person_name)"
                " SELECT f.photo_id, p.name FROM faces f"
                " JOIN persons p ON p.id = f.person_id"
                " WHERE p.name IS NOT NULL AND p.name != ''"
                f" AND f.photo_id IN ({q})"
                " GROUP BY f.photo_id", chunk)
            self.conn.execute(
                "UPDATE photos SET face_done=0, face_count=0,"
                " error=CASE WHEN error LIKE 'face:%' THEN NULL ELSE error END"
                f" WHERE id IN ({q})", chunk)
            self.conn.execute(f"DELETE FROM faces WHERE photo_id IN ({q})", chunk)
        self.conn.execute(
            "INSERT OR REPLACE INTO meta(key, value)"
            " VALUES ('face_bbox_version', ?)", (str(FACE_BBOX_VERSION),))

    def _migrate_raw_analysis_state(self) -> None:
        """0.6.30：相机 RAW 读图层上线后，一次性作废历史 RAW 的人脸 / OCR 结果。

        0.6.30 之前 faces / ocr 直接读原文件：多数相机 RAW 解码失败后永久
        滞留 face_done=0，少数 CR2 / NEF 只解出 120×160 的内嵌缩略图却被
        误标「已分析、无人脸」——升级后若不重置，这批照片永远不会重扫。

        只对 RAW 生效，普通照片一条不动；meta.raw_reader_version 保证每个库
        只执行一次，用户此后重新分析的结果不会被反复清掉。刻意不动：
        - width / height（历史尺寸记录留给完整性修复 / 重新导入更新，
          启动时逐张调 LibRaw 会拖慢首启）
        - status（保持 indexed 才能被分析链选中）
        - photo_embeddings（clip 一直有 RAW 分支，旧语义向量有效）
        """
        from photo_manager.core.rawio import (  # noqa: PLC0415 - 避免 core 层启动期耦合
            RAW_READER_VERSION, is_raw,
        )

        row = self.conn.execute(
            "SELECT value FROM meta WHERE key='raw_reader_version'").fetchone()
        try:
            seen = int(row[0]) if row else 0
        except (TypeError, ValueError):
            seen = 0
        if seen >= RAW_READER_VERSION:
            return

        rows = self.conn.execute(
            "SELECT id, file_path FROM photos WHERE media_type='photo'").fetchall()
        ids = [pid for pid, path in rows if is_raw(path)]
        # 与 pipeline.py 的照片重分析语义一致：清掉派生记录，避免重跑时重复插入。
        # 分块规避 SQLite 参数上限；UPDATE 会触发 photos_fts 同步（既有触发器行为）。
        for start in range(0, len(ids), 400):
            chunk = ids[start:start + 400]
            q = ",".join("?" * len(chunk))
            self.conn.execute(
                "UPDATE photos SET face_done=0, face_count=0, ocr_done=0,"
                " ocr_text='', has_text=0,"
                " error=CASE WHEN error LIKE 'face:%' OR error LIKE 'ocr:%'"
                " THEN NULL ELSE error END"
                f" WHERE id IN ({q})", chunk)
            self.conn.execute(f"DELETE FROM faces WHERE photo_id IN ({q})", chunk)
            self.conn.execute(f"DELETE FROM ocr_texts WHERE photo_id IN ({q})", chunk)
            self.conn.execute(f"DELETE FROM ocr_fts WHERE rowid IN ({q})", chunk)
        self.conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('raw_reader_version', ?)",
            (str(RAW_READER_VERSION),),
        )

    def _migrate_container_raw_reindex(self) -> None:
        """0.6.32：TIFF 容器型相机 RAW 修复后，把历史 .tif/.tiff 重新排队重建。

        0.6.32 起 read_bgr / 缩略图 / 预览 / 元数据对「扩展名 .tif/.tiff、
        内容是相机 RAW」的文件走 LibRaw 解码（此前扩展名不在 RAW 集合、
        全走普通图片路径）。历史库内这批照片的派生数据是坏的：一部分分析
        失败（cannot identify image file），其余宽高记成百像素内嵌缩略图、
        缩略图 / 预览 / 感知哈希 / 语义向量全部来自小图、竖拍被 EXIF tag
        二次转正。

        错误无法原位反算（需要重新解码重建），因此按 integrityRepair 的
        既有语义把它们整体置为 pending：下次「扫描入库」（含定时任务）时
        pipeline 的 pending 恢复路径会重提取元数据（LibRaw 真实尺寸）、
        重建缩略图/预览、清掉人脸/OCR/语义向量并把分析状态归零。
        普通照片与真 RAW 一条不动；meta.container_raw_reindex 保证每库
        只执行一次，避免此后每次启动都把用户的 TIFF 反复排队。
        """
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key='container_raw_reindex'").fetchone()
        if row:
            return
        self.conn.execute(
            "UPDATE photos SET status='pending', error=NULL"
            " WHERE lower(ext) IN ('.tif', '.tiff')"
            " AND status IN ('indexed', 'failed', 'error')")
        self.conn.execute(
            "INSERT OR REPLACE INTO meta(key, value)"
            " VALUES ('container_raw_reindex', '1')")

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def commit(self) -> None:
        self.conn.commit()
