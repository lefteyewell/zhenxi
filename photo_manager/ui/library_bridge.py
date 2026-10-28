"""GUI 数据桥：相册/搜索/详情/导出（QML 直调槽函数）。"""
from __future__ import annotations

from photo_manager.i18n import t as _tr

import json
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from photo_manager import models_dir
from photo_manager.core.db import Database
from photo_manager.core.extractor import QT_NATIVE_EXTS as _QT_NATIVE_EXTS
from photo_manager.core.search import PhotoSearch
from photo_manager.core.faces import MAX_DIM

log = logging.getLogger(__name__)

def _autostart_apply(on: bool) -> bool:
    """写入/移除系统级开机自启条目（0.5.48）。返回是否成功。

    绿色便携、无需安装器、无需管理员：
    - Windows：HKCU\\...\\CurrentVersion\\Run 注册表（当前用户键）；
    - Linux/麒麟：~/.config/autostart/PhotoManager.desktop（XDG 标准，UKUI 支持）。
    记录的是程序当前路径，故启用后移动文件夹需取消再勾选。
    """
    from PySide6.QtCore import QCoreApplication

    exe = QCoreApplication.applicationFilePath()
    if sys.platform.startswith("win"):
        import winreg

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE)
        except OSError:
            return False
        with key:
            try:
                if on:
                    winreg.SetValueEx(key, "PhotoManager", 0, winreg.REG_SZ,
                                      f'"{exe}"')
                else:
                    try:
                        winreg.DeleteValue(key, "PhotoManager")
                    except FileNotFoundError:
                        pass
                return True
            except OSError:
                return False
    # Linux / 银河麒麟（UKUI 遵循 XDG autostart）
    try:
        p = Path.home() / ".config" / "autostart" / "PhotoManager.desktop"
        if on:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=PhotoManager\n"
                f'Exec="{exe}"\n'
                "Icon=PhotoManager\n"
                "X-GNOME-Autostart-enabled=true\n"
                "Comment=照片管理系统（开机自启）\n",
                encoding="utf-8")
        else:
            p.unlink(missing_ok=True)

        return True
    except OSError:
        return False

class LibraryBridge(QObject):
    photosChanged = Signal()
    photoSelected = Signal(int)
    message = Signal(str)
    taskProgress = Signal(int, int, str)
    toast = Signal(str, str)  # (text, kind) 终态轻提示
    # 0.5.53：后台任务队列（current=正在执行的第几项，1 起；0=尚未开始；
    # stagesJson=["阶段名", ...]）——进度弹窗据此显示任务列表
    chainProgress = Signal(int, int, str)
    busyChanged = Signal()  # 任务互斥获取/释放（弹窗解除隐藏抑制等）
    galleryGroupViewChanged = Signal(bool)  # 中间栏「分组视图」开关（0.5.55）
    integrityFinished = Signal(str)  # 完整性校验完成（JSON 摘要）
    similarFinished = Signal(str)  # 以图搜图完成（JSON 摘要）
    sceneSuggestionsFinished = Signal(str)  # 场景建议完成（JSON，0.5.27）
    stacksDetected = Signal(int)  # 堆叠检测成功且栈数>0（0.5.32，图库自动切堆叠视图）
    clipAutoIndexChanged = Signal(bool)  # 自动语义索引开关变化（0.5.46，菜单/工具/设置三处联动）
    autoStartChanged = Signal(bool)  # 开机自启开关变化（0.5.48，设置里唯一入口）
    trayEnabledChanged = Signal(bool)  # 关闭到托盘开关变化（0.5.48，设置里唯一入口）

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        from photo_manager.i18n import set_lang as _set_lang
        _set_lang(self.uiLang())
        self.db = Database(db_path).connect()
        # 0.5.64：OS 定时任务注册状态缓存（None=未查询；setScheduleEngine 时失效）
        self._os_registered_cache: bool | None = None
        # 0.5.51：一次性把断链的绝对缩略图路径改写为相对路径（便携化）
        self._migrate_thumb_paths()
        # 0.5.46：自动语义索引开关（默认开）。进程内以 self._clip_auto 为单一真值
        # （QSettings 多实例读取存在跨实例缓存不一致），QSettings 仅作跨重启持久化。
        from PySide6.QtCore import QSettings as _QS

        # ⚠️ 必须 type=bool：Windows 注册表把 bool 存成 "false"/"true" 字符串，
        # bool("false") == True——0.5.55 修复（否则用户设为关的开关重启后静默变回开）。
        self._clip_auto = bool(
            _QS("PhotoManager", "PhotoManager").value("clipAutoIndex", True, type=bool))
        self._group_view = bool(
            _QS("PhotoManager", "PhotoManager").value("ui/groupView", False, type=bool))
        # 0.5.48：开机自启（默认关）/ 关闭窗口到托盘（默认开）。
        # 同样以进程内真值避免 QSettings 跨实例缓存不一致（0.5.46 坑）。
        self._auto_start = bool(
            _QS("PhotoManager", "PhotoManager").value("autoStart", False, type=bool))
        self._tray_enabled = bool(
            _QS("PhotoManager", "PhotoManager").value("trayEnabled", True, type=bool))
        # 0.5.67：启动窗口最大化（默认开）
        self._startup_maximized = bool(
            _QS("PhotoManager", "PhotoManager").value("ui/startMaximized", True, type=bool))
        # 0.5.49：自动语义索引挂起标志（分析链占用 _busy 时暂存，链尾接续）
        self._clip_pending = False
        # 0.5.67：人脸聚类相似度阈值（用户可调，0.40~0.70）。
        # 0.6.9：默认 0.50 → 0.60（用户实测 0.5 偏松易误并）。
        # 进程内单一真值 + QSettings 持久化（同上，避免跨实例缓存不一致）。
        try:
            self._face_threshold = min(0.70, max(0.40, float(
                _QS("PhotoManager", "PhotoManager")
                .value("faces/clusterThreshold", 0.6, type=float))))
        except (TypeError, ValueError):
            self._face_threshold = 0.6
        # 0.6.9：分析并行度（"auto"=自动留 2 核 / "full"=全速占满核 /
        # "custom"=自定义进程数），见 analysisParallelMode 槽。
        self._parallel_mode = str(_QS("PhotoManager", "PhotoManager")
                                  .value("analysis/parallelMode", "auto"))
        if self._parallel_mode not in ("auto", "full", "custom"):
            self._parallel_mode = "auto"
        try:
            self._parallel_custom = int(_QS("PhotoManager", "PhotoManager")
                                        .value("analysis/parallelCustom", 4,
                                               type=int))
        except (TypeError, ValueError):
            self._parallel_custom = 4
        self.search = PhotoSearch(self.db)
        self._busy = 0
        self._busy_lock = threading.Lock()
        self._cancel = threading.Event()
        self._tree_expanded: set[str] = set()
        self._dir_cache: dict[str, str] | None = None
        self._direct_cache: set[str] | None = None
        self._integrity: dict | None = None  # 最近一次完整性校验报告
        self._similar: list[tuple[int, float]] = []  # 最近一次以图搜图结果 (photo_id, score)
        self._face_search: list[tuple[int, float]] = []  # 最近一次上传人脸搜图结果
        # 0.5.36：图库排序（持久化），作用于 photos() 与 _photo_rows() 的所有列表视图
        self._gallery_sort = self._load_gallery_sort()
        self.photosChanged.connect(self._invalidate_dir_caches)

    # 图库排序键 → ORDER BY 子句（白名单，防注入；键不合法一律回退默认）
    GALLERY_SORTS: dict[str, str] = {
        "time_desc": "sort_key DESC, id DESC",      # 拍摄时间 新→旧（默认）
        "time_asc": "sort_key ASC, id ASC",         # 拍摄时间 旧→新
        "name": "file_name COLLATE NOCASE ASC, id ASC",          # 文件名 A→Z
        "folder": "file_path COLLATE NOCASE ASC, sort_key DESC",  # 文件夹/路径
        "camera": "camera_model COLLATE NOCASE ASC, sort_key DESC",  # 相机型号
        "rating": "rating DESC, sort_key DESC, id DESC",          # 评级 高→低
        "size": "file_size DESC, id DESC",          # 文件大小 大→小
    }

    def _load_gallery_sort(self) -> str:
        from PySide6.QtCore import QSettings
        v = QSettings("PhotoManager", "PhotoManager").value("ui/gallerySort", "time_desc")
        return v if v in self.GALLERY_SORTS else "time_desc"

    def _sort_sql(self, prefix: str = "") -> str:
        p = f"{prefix}." if prefix else ""
        return ", ".join(p + clause.strip() for clause in
                         self.GALLERY_SORTS[self._gallery_sort].split(","))

    def _invalidate_dir_caches(self):
        """照片变化（入库/移出/删除）后失效目录树缓存。"""
        self._dir_cache = None
        self._direct_cache = None

    def _finish(self, msg: str) -> None:
        """终态反馈：状态栏 + Toast 双发，kind 依消息内容判定。

        0.5.52 修复：形如「完成：计算 N 张，失败 0」的**成功汇总**此前因字面
        含「失败」两字被误标为红色 error——用户在自动分析链的重复检测阶段
        （人脸检测之前）看到的「一闪而过的红色弹窗」即此。现失败数为 0 的
        汇总不再判红；真正的失败（「失败：异常」/「失败 N 张」N>0）仍为红色。
        """
        if "失败" in msg and not re.search(r"失败\s*0+([^0-9]|$)", msg):
            kind = "error"
        elif "取消" in msg or "中断" in msg:
            kind = "warning"
        else:
            kind = "success"
        self.message.emit(msg)
        self.toast.emit(msg, kind)

    @Slot(result=int)
    def busyCount(self) -> int:
        return self._busy

    # ---------- 统计 ----------
    @Slot(result=str)
    def statsText(self) -> str:
        c = self.db.conn
        photos = c.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0"
        ).fetchone()[0]
        faces = c.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
        persons = c.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        events = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        texted = c.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0 AND has_text=1"
        ).fetchone()[0]
        return _tr("照片 {p1} · 事件 {p2} · 人脸 {p3}（{p4} 人）· 含文字 {p5}").format(p1=photos, p2=events, p3=faces, p4=persons, p5=texted)

    # ---------- 相册 ----------
    @Slot(int, int, result="QVariant")
    def photos(self, offset: int = 0, limit: int = 500) -> list[dict]:
        rows = self.db.conn.execute(
            " SELECT id, thumbnail_path, file_name, taken_at, face_count, has_text,"
            " camera_model, file_path, width, height, rating, flag, color_label,"
            " media_type, duration FROM photos"
            " WHERE status != 'missing' AND archived = 0"
            f" ORDER BY {self._sort_sql()} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return self._pack(rows)

    @Slot(int, int, result="QVariant")
    def photosByFolder(self, offset: int = 0, limit: int = 500) -> list[dict]:
        """分组视图数据源（0.5.55）：固定按文件路径排序（组间有序、组内相邻），
        不读改用户的排序设置。"""
        rows = self._photo_rows("1=1", (), limit, offset,
                                order_by="file_path COLLATE NOCASE ASC, sort_key DESC")
        return self._pack(rows)

    @Slot(result=bool)
    def galleryGroupView(self) -> bool:
        """中间栏「分组视图」开关（0.5.55，QSettings ui/groupView，默认关）。"""
        return getattr(self, "_group_view", False)

    @Slot(bool)
    def setGalleryGroupView(self, on: bool) -> None:
        from PySide6.QtCore import QSettings

        on = bool(on)
        self._group_view = on
        qs = QSettings("PhotoManager", "PhotoManager")
        qs.setValue("ui/groupView", on)
        qs.sync()
        self.galleryGroupViewChanged.emit(on)

    @Slot(result=str)
    def gallerySort(self) -> str:
        """当前图库排序键（0.5.36，QML 启动时同步按钮文案）。"""
        return self._gallery_sort

    @Slot(str)
    def setGallerySort(self, key: str) -> None:
        """设置图库排序并持久化；仅接受白名单键。"""
        from PySide6.QtCore import QSettings
        if key not in self.GALLERY_SORTS:
            return
        self._gallery_sort = key
        QSettings("PhotoManager", "PhotoManager").setValue("ui/gallerySort", key)

    @Slot(result="QVariant")
    def totalPhotos(self) -> int:
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0"
        ).fetchone()[0]

    @Slot(str, int, int, result="QVariant")
    def onThisDay(self, monthDay: str = "", offset: int = 0, limit: int = 2000) -> list[dict]:
        """往年今日：返回拍摄于指定月-日（MM-DD，默认今天）的历史照片（不含今年）。

        每条含 year 字段（int），供前端按年分组展示。缩略图解析为可加载的 URL。
        """
        from photo_manager.core.search import on_this_day

        rows = on_this_day(self.db, monthDay, limit, offset)
        out = []
        for r in rows:
            d = dict(r)
            d["thumb"] = self._thumb_url(r["thumb"])
            out.append(d)
        return out

    @Slot(int, int, int, result="QVariant")
    def eventPhotos(self, event_id: int, offset: int = 0, limit: int = 500) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT p.id, p.thumbnail_path, p.file_name, p.taken_at, p.face_count,"
            " p.has_text, p.camera_model, p.file_path, p.width, p.height,"
            " p.rating, p.flag, p.color_label"
        " FROM event_photos ep JOIN photos p ON p.id = ep.photo_id"
        " WHERE ep.event_id=? AND p.status != 'missing' AND p.archived = 0"
        f" ORDER BY {self._sort_sql('p')} LIMIT ? OFFSET ?",
            (event_id, limit, offset),
        ).fetchall()
        return self._pack(rows)

    # ---------- 分类浏览：文件夹 / 人物 / 地点 / 设备 ----------
    def _photo_rows(self, where: str, params: tuple, limit, offset,
                    order_by: str | None = None) -> list[tuple]:
        """通用照片行查询（排除 missing 与已归档，按时间倒序分页）。

        order_by 非空时覆盖用户排序（0.5.55：分组视图固定按文件路径排序）。

        已归档照片默认从所有普通浏览中隐藏（归档视图与显式 archived: 搜索除外），
        与"程序内不删除、仅隐藏"的归档语义一致。
        """
        return self.db.conn.execute(
            " SELECT id, thumbnail_path, file_name, taken_at, face_count, has_text,"
            " camera_model, file_path, width, height, rating, flag, color_label,"
            " media_type, duration, decode_error FROM photos"
            f" WHERE status != 'missing' AND archived = 0 AND {where}"
            f" ORDER BY {order_by or self._sort_sql()} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()

    @Slot(str, result="QVariant")
    def folderTree(self, root: str = "") -> list[dict]:
        """按 folder_path 的目录层级构建树（节点含名称/完整路径/照片数/子节点）。

        root 为空返回整棵树的顶层分支；否则返回该节点下直接子分支（惰性展开用）。
        """
        rows = self.db.conn.execute(
            "SELECT DISTINCT folder_path FROM photos"
            " WHERE folder_path IS NOT NULL AND folder_path != ''"
        ).fetchall()
        paths = {r[0] for r in rows}
        prefix = root.rstrip("/\\") + ("/" if root else "")
        kids: dict[str, list[str]] = {}
        for p in paths:
            if root and not (p == root or p.startswith(prefix)):
                continue
            rel = p[len(prefix):] if root else p
            first = (rel.split("/")[0] if "/" in rel else rel).strip()
            if not first:
                continue
            if root:
                node = prefix + first
            else:
                node = first
            kids.setdefault(node, []).append(p)
        out = []
        for node, leaves in kids.items():
            # 0.6.10：计数拆 = + GLOB 前缀两段（均可走 idx_photos_folder
            # 定位；原 OR+LIKE 是整索引扫描，节点数 × 全扫，UI 线程卡顿）
            cnt = self.db.conn.execute(
                "SELECT (SELECT COUNT(*) FROM photos WHERE folder_path = ?)"
                " + (SELECT COUNT(*) FROM photos WHERE folder_path GLOB ?)",
                (node, self._glob_escape(node) + "/*"),
            ).fetchone()[0]
            out.append({"name": node.rsplit("/", 1)[-1], "path": node,
                        "photoCount": cnt, "hasChildren": len(leaves) > 1,
                        "isRoot": not root})
        out.sort(key=lambda d: (not d["isRoot"], d["name"].lower()))
        return out

    @staticmethod
    def _glob_escape(s: str) -> str:
        """GLOB 通配符转义（GLOB 无 ESCAPE 子句，用括号字面量表达）。"""
        return (s.replace("[", "[[]").replace("*", "[*]")
                 .replace("?", "[?]"))

    @staticmethod
    def _folder_cond(node: str) -> tuple[str, list]:
        """folder_path 的"本目录或子目录"条件（0.6.10 索引友好版）。

        原写法 `folder_path = ? OR folder_path LIKE ?` 因 OR + 大小写不敏感
        LIKE 无法走索引定位（EXPLAIN = 整索引扫描），弱机文件夹树每次
        展开/翻页都全扫，UI 线程直接被拖死。GLOB 前缀大小写敏感、可走
        idx_photos_folder 范围定位（EXPLAIN = SEARCH）；目录树节点本就取自
        库里存储的 folder_path 值，与子级的大小写必然一致，GLOB 更精确。"""
        return ("(folder_path = ? OR folder_path GLOB ?)",
                [node, LibraryBridge._glob_escape(node) + "/*"])

    @Slot(str, int, int, result="QVariant")
    def folderPhotos(self, folder: str, offset: int = 0, limit: int = 500) -> list[dict]:
        """某文件夹及其所有子级下的照片。"""
        where, params = self._folder_cond(folder)
        return self._pack(self._photo_rows(where, params, limit, offset))

    @Slot(str, result=int)
    def folderCount(self, folder: str) -> int:
        cond, params = self._folder_cond(folder)
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0 AND"
            f" {cond}", params,
        ).fetchone()[0]

    def _person_display_map(self) -> dict[int, str]:
        """persons.id → 显示名。

        未命名人物按 id 顺序自动编号显示为「人物 1/人物 2/…」；
        用户重命名后（renamePerson）显示人名。编号仅是显示名，不写库，
        因此聚类重建（FaceClusterer 会清空 persons 重建）后编号自动重排。
        """
        rows = self.db.conn.execute(
            "SELECT id, COALESCE(name,'') FROM persons ORDER BY id"
        ).fetchall()
        out: dict[int, str] = {}
        seq = 0
        for pid, name in rows:
            if not name:
                seq += 1
                name = _tr("人物 {p1}").format(p1=seq)
            out[pid] = name
        return out

    @Slot(result="QVariant")
    def people(self) -> list[dict]:
        """人物列表：基于人脸聚类（person_id>0）与未命名簇。

        0.5.28：附带代表头像——取该人物置信度最高的一张脸，返回其缩略图路径
        与像素级裁剪框（avatarSrc/X/Y/W/H），QML 用 Image.sourceRect 裁出人像，
        便于按长相命名；无脸数据或文件缺失时不带字段（QML 回退图标）。
        """
        conn = self.db.conn
        names = self._person_display_map()
        # 0.6.10：原实现每人 2 次聚合查询（人数×2 次全表扫描，faces 无
        # person_id 索引时更糟），弱机后台任务期间直接把 UI 线程饿死
        # （麒麟实测点人脸假死）。改为 2 条 GROUP BY 一次取全 +
        # idx_faces_person 索引（db.py 同步新增）。
        counts = {r[0]: r[1] for r in conn.execute(
            "SELECT person_id, COUNT(DISTINCT photo_id) FROM faces"
            " WHERE hidden=0 GROUP BY person_id")}
        blurs = {r[0]: r[1] for r in conn.execute(
            "SELECT person_id, AVG(blur) FROM faces"
            " WHERE hidden=0 AND blur IS NOT NULL AND blur >= 0"
            " GROUP BY person_id")}
        out = []
        for pid in sorted(names):
            item = {"id": pid, "name": names[pid],
                    "photoCount": counts.get(pid, 0)}
            # 0.5.37：人物平均模糊指数（未评分/文件缺失的脸不参与均值）
            b = blurs.get(pid)
            item["blurIdx"] = round(b) if b is not None else -1
            if pid > 0:
                row = conn.execute(
                    "SELECT f.bbox, p.file_path, p.thumbnail_path, p.width, p.height,"
                    " p.thumb_width, p.thumb_height"
                    " FROM faces f JOIN photos p ON p.id = f.photo_id"
                    " WHERE f.person_id=? AND f.hidden=0 ORDER BY f.score DESC LIMIT 1", (pid,),
                ).fetchone()
            else:  # 未命名人物（id 0）：任取一张未指派的脸
                row = conn.execute(
                    "SELECT f.bbox, p.file_path, p.thumbnail_path, p.width, p.height,"
                    " p.thumb_width, p.thumb_height"
                    " FROM faces f JOIN photos p ON p.id = f.photo_id"
                    " WHERE (f.person_id IS NULL OR f.person_id='') AND f.hidden=0"
                    " ORDER BY f.score DESC LIMIT 1",
                ).fetchone()
            av = self._face_avatar(row)
            if av:
                item.update(av)
            out.append(item)
        unseen = conn.execute(
            "SELECT COUNT(DISTINCT photo_id) FROM faces"
            " WHERE (person_id IS NULL OR person_id='') AND hidden=0"
        ).fetchone()[0]
        if unseen:
            out.append({"id": 0, "name": "未命名人物", "photoCount": unseen,
                        "unassigned": True})
        return out

    @staticmethod
    def _face_avatar(row) -> dict | None:
        """由 (bbox, file_path, thumbnail_path, w, h, tw, th) 行算头像裁剪框。

        bbox 是检测缩放图（最长边 ≤ MAX_DIM）坐标，与 photoFaces 同一套归一化
        口径；归一化坐标与分辨率无关，可直接映射到缩略图或原图像素。
        """
        import json

        if not row:
            return None
        bbox, fpath, tpath, w, h, tw, th = row
        if not (w and h):
            return None
        try:
            bx, by, bw, bh = json.loads(bbox)
        except Exception:
            return None
        scale = min(1.0, MAX_DIM / max(h, w)) if max(h, w) > 0 else 1.0
        sw = max(1, round(w * scale))
        sh = max(1, round(h * scale))
        nx, ny, nw, nh = bx / sw, by / sh, bw / sw, bh / sh
        if tpath and tw and th and Path(tpath).exists():
            src, rw, rh = tpath, tw, th
        elif fpath and Path(fpath).exists():
            src, rw, rh = fpath, w, h
        else:
            return None
        return {
            "avatarSrc": src,
            "avatarX": max(0, round(nx * rw)),
            "avatarY": max(0, round(ny * rh)),
            "avatarW": max(1, round(nw * rw)),
            "avatarH": max(1, round(nh * rh)),
        }

    @Slot(int, int, int, result="QVariant")
    def personPhotos(self, person_id: int, offset: int = 0, limit: int = 500) -> list[dict]:
        where = ("EXISTS (SELECT 1 FROM faces f WHERE f.photo_id = photos.id"
                 " AND f.person_id = ? AND f.hidden = 0)")
        return self._pack(self._photo_rows(where, (person_id,), limit, offset))

    @Slot(int, result=int)
    def personCount(self, person_id: int) -> int:
        conn = self.db.conn
        if person_id == 0:
            where = "person_id IS NULL OR person_id=''"
        else:
            where = "person_id=?"
        return conn.execute(
            "SELECT COUNT(DISTINCT photo_id) FROM faces"
            " WHERE hidden=0 AND " + where,
            () if person_id == 0 else (person_id,),
        ).fetchone()[0]

    @Slot(int, str, result=bool)
    def renamePerson(self, person_id: int, name: str) -> bool:
        """给人物命名；重名（persons.name UNIQUE）返回 False。"""
        name = (name or "").strip()
        if person_id <= 0 or not name:
            return False
        conn = self.db.conn
        try:
            conn.execute("UPDATE persons SET name=? WHERE id=?", (name, person_id))
            conn.commit()
        except Exception:
            conn.rollback()
            return False
        return True

    @Slot(str, result=int)
    def newPerson(self, name: str = "") -> int:
        """新建人物（空名=未命名人物），返回新 id。"""
        name = (name or "").strip() or None
        conn = self.db.conn
        try:
            cur = conn.execute(
                "INSERT INTO persons(name, face_count) VALUES (?, 0)", (name,)
            )
            conn.commit()
            return cur.lastrowid
        except Exception:
            conn.rollback()
            return 0

    @Slot(int, int, result=int)
    def mergePersons(self, src_id: int, dst_id: int) -> int:
        """把 src 人物的全部脸并入 dst 人物（0=未命名人物）；删除 src 行。"""
        conn = self.db.conn
        try:
            conn.execute("BEGIN")
            if src_id == 0:
                conn.execute("UPDATE faces SET person_id=? WHERE person_id IS NULL"
                             " OR person_id=''", (None if dst_id == 0 else dst_id,))
            else:
                conn.execute("UPDATE faces SET person_id=? WHERE person_id=?",
                             (None if dst_id == 0 else dst_id, src_id))
                conn.execute("DELETE FROM persons WHERE id=?", (src_id,))
            for pid in {dst_id} if dst_id > 0 else set():
                conn.execute(
                    "UPDATE persons SET face_count=(SELECT COUNT(*) FROM faces"
                    " WHERE person_id=?) WHERE id=?", (dst_id, dst_id))
            conn.commit()
            return 1
        except Exception:
            conn.rollback()
            return 0

    @Slot("QVariant", int, result=int)
    def movePhotosToPerson(self, ids, person_id: int) -> int:
        """把整张照片的所有脸移到指定人物（0=移回未命名）。"""
        from PySide6.QtQml import QJSValue

        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        ids = [int(i) for i in (ids or [])]
        if not ids:
            return 0
        conn = self.db.conn
        try:
            conn.execute("BEGIN")
            conn.executemany(
                "UPDATE faces SET person_id=? WHERE photo_id=?",
                [(None if person_id <= 0 else person_id, pid) for pid in ids],
            )
            if person_id > 0:
                conn.execute(
                    "UPDATE persons SET face_count=(SELECT COUNT(*) FROM faces"
                    " WHERE person_id=?) WHERE id=?", (person_id, person_id))
            conn.commit()
            return len(ids)
        except Exception:
            conn.rollback()
            return 0

    @Slot(int, result="QVariant")
    def photoFaces(self, photo_id: int) -> list[dict]:
        """照片内的人脸列表：bbox（检测图坐标）+ 归一化坐标 + 所属人物。

        bbox 存的是检测缩放图（最长边 ≤ 2000）坐标；归一化坐标 = bbox / 缩放图尺寸，
        供 QML 按实际显示尺寸叠加人脸框。"""
        rows = self.db.conn.execute(
            "SELECT f.id, f.bbox, f.score, f.person_id, f.blur,"
            " COALESCE(p.name, '') FROM faces f"
            " LEFT JOIN persons p ON p.id = f.person_id"
            " WHERE f.photo_id=? AND f.hidden=0 ORDER BY f.id", (photo_id,),
        ).fetchall()
        photo = self.db.conn.execute(
            "SELECT width, height FROM photos WHERE id=?", (photo_id,)
        ).fetchone()
        if not photo:
            return []
        w, h = photo[0] or 0, photo[1] or 0
        import json

        display = self._person_display_map()
        scale = min(1.0, MAX_DIM / max(h, w)) if max(h, w) > 0 else 1.0
        sw = max(1, round(w * scale))
        sh = max(1, round(h * scale))
        out = []
        for rid, bbox, score, pid, blur, pname in rows:
            try:
                bx, by, bw, bh = json.loads(bbox)
            except Exception:
                continue
            out.append({
                "id": rid,
                "bbox": [bx, by, bw, bh],
                "score": score or 0,
                "personId": pid or 0,
                "personName": display.get(pid) or "未命名人物",
                "blurIdx": int(blur) if blur is not None else -1,
                "nx": bx / sw, "ny": by / sh,
                "nw": bw / sw, "nh": bh / sh,
            })
        return out

    @Slot(int, result=bool)
    def dismissFace(self, face_id: int) -> bool:
        """人工取消误检"人脸"（动物脸/模糊块）：删除该 faces 行并同步 face_count。

        原图与人脸检测流水线不受影响；对该照片重新运行人脸识别会重新检出。
        """
        conn = self.db.conn
        row = conn.execute(
            "SELECT photo_id FROM faces WHERE id=?", (face_id,)
        ).fetchone()
        if not row:
            return False
        pid = row[0]
        conn.execute("DELETE FROM faces WHERE id=?", (face_id,))
        conn.execute(
            "UPDATE photos SET face_count=(SELECT COUNT(*) FROM faces WHERE photo_id=?)"
            " WHERE id=?",
            (pid, pid),
        )
        conn.commit()
        self.photosChanged.emit()
        return True

    @Slot(int, int, result=bool)
    def assignFace(self, face_id: int, person_id: int) -> bool:
        """把单张人脸指派到指定人物（0=移回未命名）。用于多人照片逐脸区分。"""
        conn = self.db.conn
        try:
            conn.execute(
                "UPDATE faces SET person_id=? WHERE id=?",
                (None if person_id <= 0 else person_id, face_id),
            )
            if person_id > 0:
                conn.execute(
                    "UPDATE persons SET face_count=(SELECT COUNT(*) FROM faces"
                    " WHERE person_id=?) WHERE id=?", (person_id, person_id))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    @Slot(int, result="QVariant")
    def personFaceList(self, person_id: int) -> list[dict]:
        """人物（0=未命名）的全部人脸清单：头像裁剪框 + 所在照片信息。

        0.5.67 人物批量分拆：人物页「管理头像」弹出的人脸网格数据源。"""
        conn = self.db.conn
        if person_id > 0:
            rows = conn.execute(
                "SELECT f.id, f.photo_id, f.person_id, f.blur, f.bbox, p.file_path,"
                " p.thumbnail_path, p.width, p.height, p.thumb_width, p.thumb_height,"
                " p.file_name FROM faces f JOIN photos p ON p.id = f.photo_id"
                " WHERE f.person_id=? AND f.hidden=0 ORDER BY f.photo_id, f.id",
                (person_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT f.id, f.photo_id, f.person_id, f.blur, f.bbox, p.file_path,"
                " p.thumbnail_path, p.width, p.height, p.thumb_width, p.thumb_height,"
                " p.file_name FROM faces f JOIN photos p ON p.id = f.photo_id"
                " WHERE (f.person_id IS NULL OR f.person_id='') AND f.hidden=0"
                " ORDER BY f.photo_id, f.id",
            ).fetchall()
        out = []
        for r in rows:
            item = {"faceId": r[0], "photoId": r[1], "personId": r[2] or 0,
                    "blurIdx": round(r[3]) if r[3] is not None else -1,
                    "name": r[11]}
            av = self._face_avatar((r[4], r[5], r[6], r[7], r[8], r[9], r[10]))
            if av:
                item.update(av)
            out.append(item)
        return out

    @Slot(result=float)
    def faceClusterThreshold(self) -> float:
        """人脸聚类相似度阈值（0.40~0.70，默认 0.60；越大越严格）。

        0.5.67 开放给用户：设置 → 智能分析 → 人脸聚类相似度阈值。
        0.6.9：默认 0.50 → 0.60。改动后需重新执行「人脸聚类」才生效。"""
        return float(getattr(self, "_face_threshold", 0.6))

    @Slot(float)
    def setFaceClusterThreshold(self, v: float) -> None:
        v = min(0.70, max(0.40, float(v)))
        self._face_threshold = v
        from PySide6.QtCore import QSettings

        QSettings("PhotoManager", "PhotoManager").setValue(
            "faces/clusterThreshold", v)

    # ---------- 0.6.9 分析并行度（设置 → 智能分析） ----------

    @Slot(result=str)
    def analysisParallelMode(self) -> str:
        """分析并行度模式："auto"（默认，留 2 核）/"full"（占满核）/"custom"。"""
        return getattr(self, "_parallel_mode", "auto")

    @Slot(str)
    def setAnalysisParallelMode(self, mode: str) -> None:
        mode = str(mode)
        if mode not in ("auto", "full", "custom"):
            mode = "auto"
        self._parallel_mode = mode
        from PySide6.QtCore import QSettings

        QSettings("PhotoManager", "PhotoManager").setValue(
            "analysis/parallelMode", mode)

    @Slot(result=int)
    def analysisParallelCustom(self) -> int:
        """自定义并行进程数（仅 mode=="custom" 时生效）。"""
        return int(getattr(self, "_parallel_custom", 4))

    @Slot(int)
    def setAnalysisParallelCustom(self, n: int) -> None:
        self._parallel_custom = max(1, min(int(n), 16))
        from PySide6.QtCore import QSettings

        QSettings("PhotoManager", "PhotoManager").setValue(
            "analysis/parallelCustom", self._parallel_custom)

    def _analysis_workers(self) -> int:
        """按设置换算分析进程数；auto 返回 0（管线内部走默认钳制逻辑）。"""
        from photo_manager.core.system import analysis_workers

        mode = getattr(self, "_parallel_mode", "auto")
        if mode == "custom":
            return analysis_workers("custom",
                                    int(getattr(self, "_parallel_custom", 4)))
        if mode == "full":
            return analysis_workers("full")
        return 0

    @Slot("QVariant", int, str, result=int)
    def moveFacesToPerson(self, face_ids, person_id: int, new_name: str = "") -> int:
        """批量把人脸移到指定人物（0=未命名；-1=新建人物，new_name 可选命名）。

        0.5.67 人物分拆：只改归属标签，不动特征向量；来源人物 face_count
        同步重算，散空的未命名人物行清理（与合并行为对齐）。返回移动数。"""
        from PySide6.QtQml import QJSValue

        if isinstance(face_ids, QJSValue):
            face_ids = face_ids.toVariant()
        ids = [int(i) for i in (face_ids or [])]
        if not ids:
            return 0
        conn = self.db.conn
        try:
            conn.execute("BEGIN")
            if person_id == -1:
                cur = conn.execute("INSERT INTO persons(name) VALUES(?)",
                                   (new_name or None,))
                person_id = cur.lastrowid
            marks = ",".join("?" * len(ids))
            olds = {r[0] for r in conn.execute(
                f"SELECT DISTINCT person_id FROM faces WHERE id IN ({marks})",
                ids).fetchall() if r[0]}
            conn.execute(
                f"UPDATE faces SET person_id=? WHERE id IN ({marks})",
                (None if person_id <= 0 else person_id, *ids),
            )
            if person_id > 0:
                olds.add(person_id)
            for op in olds:
                conn.execute(
                    "UPDATE persons SET face_count=(SELECT COUNT(*) FROM faces"
                    " WHERE person_id=?) WHERE id=?", (op, op))
                if op != person_id:
                    left = conn.execute(
                        "SELECT COUNT(*) FROM faces WHERE person_id=?",
                        (op,)).fetchone()[0]
                    has_name = conn.execute(
                        "SELECT COALESCE(name,'') FROM persons WHERE id=?",
                        (op,)).fetchone()[0]
                    if left == 0 and not has_name:
                        conn.execute("DELETE FROM persons WHERE id=?", (op,))
            conn.commit()
            return len(ids)
        except Exception:
            conn.rollback()
            log.exception("批量移动人脸失败")
            return 0

    @Slot(int, result=str)
    def faceCropUrl(self, face_id: int) -> str:
        """生成单张人脸的裁剪缩略图（按 bbox 从原图裁剪，存缓存目录），返回 URL。"""
        row = self.db.conn.execute(
            "SELECT f.photo_id, f.bbox, p.file_path, p.width, p.height"
            " FROM faces f JOIN photos p ON p.id = f.photo_id WHERE f.id=?",
            (face_id,),
        ).fetchone()
        if not row:
            return ""
        import json
        from PySide6.QtCore import QUrl

        photo_id, bbox, file_path, w, h = row
        fp = self._resolve(file_path)
        if fp is None:
            return ""
        try:
            bx, by, bw, bh = json.loads(bbox)
        except Exception:
            return ""
        scale = min(1.0, MAX_DIM / max(h, w)) if max(h, w) > 0 else 1.0
        x = int(bx / scale)
        y = int(by / scale)
        cw = int(bw / scale)
        ch = int(bh / scale)
        try:
            from PIL import Image, ImageOps

            with Image.open(fp) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                ww, hh = im.size
                x = max(0, min(x, ww - 1))
                y = max(0, min(y, hh - 1))
                cw = max(8, min(cw, ww - x))
                ch = max(8, min(ch, hh - y))
                crop = im.crop((x, y, x + cw, y + ch))
                crop.thumbnail((160, 160))
                cache_dir = Path(tempfile.gettempdir()) / "pm_faces"
                cache_dir.mkdir(parents=True, exist_ok=True)
                out = cache_dir / f"face_{face_id}.jpg"
                crop.save(out, "JPEG", quality=85)
                return QUrl.fromLocalFile(str(out)).toString()
        except Exception:
            return ""

    @Slot("QVariant", result=int)
    def mergePeople(self, ids) -> int:
        """把多个人物合并到第一个（批量合并，C4）。返回受影响人数。"""
        from PySide6.QtQml import QJSValue

        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        ids = [int(i) for i in (ids or []) if int(i) > 0]
        if len(ids) < 2:
            return 0
        dst = ids[0]
        srcs = ids[1:]
        conn = self.db.conn
        try:
            conn.execute("BEGIN")
            for src in srcs:
                conn.execute("UPDATE faces SET person_id=? WHERE person_id=?",
                             (dst, src))
                conn.execute("DELETE FROM persons WHERE id=?", (src,))
            conn.execute(
                "UPDATE persons SET face_count=(SELECT COUNT(*) FROM faces"
                " WHERE person_id=?) WHERE id=?", (dst, dst))
            conn.commit()
            return len(srcs)
        except Exception:
            conn.rollback()
            return 0

    @Slot(result="QVariant")
    def restoreAllMovedOut(self) -> list[str]:
        """恢复全部已移出目录（回收站一键全恢复）。返回处理的目录列表。"""
        rows = self.db.conn.execute(
            "SELECT DISTINCT dest_dir FROM move_out_records"
        ).fetchall()
        dirs = [r[0] for r in rows]
        for d in dirs:
            self.reimportMovedOut(d)
        return dirs

    @Slot(result="QVariant")
    def locations(self) -> list[dict]:
        """地点列表：按 GPS 坐标聚合（保留一定精度）。"""
        rows = self.db.conn.execute(
            "SELECT ROUND(gps_lat, 2), ROUND(gps_lon, 2), COUNT(*) FROM photos"
            " WHERE status != 'missing' AND gps_lat IS NOT NULL AND gps_lon IS NOT NULL"
            " GROUP BY 1, 2 ORDER BY 3 DESC"
        ).fetchall()
        return [{"lat": r[0], "lon": r[1], "name": f"{r[0]:.2f}, {r[1]:.2f}",
                 "photoCount": r[2]} for r in rows]

    @Slot(float, float, int, int, result="QVariant")
    def locationPhotos(self, lat: float, lon: float, offset: int = 0,
                       limit: int = 500) -> list[dict]:
        where = "ROUND(gps_lat,2)=? AND ROUND(gps_lon,2)=?"
        return self._pack(self._photo_rows(where, (lat, lon), limit, offset))

    @Slot(float, float, result=int)
    def locationCount(self, lat: float, lon: float) -> int:
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND"
            " ROUND(gps_lat,2)=? AND ROUND(gps_lon,2)=?",
            (lat, lon),
        ).fetchone()[0]

    @Slot(result="QVariant")
    def devices(self) -> list[dict]:
        """设备列表：按相机型号聚合。"""
        rows = self.db.conn.execute(
            "SELECT camera_make, camera_model, COUNT(*) FROM photos"
            " WHERE status != 'missing' AND camera_model IS NOT NULL"
            " AND camera_model != ''"
            " GROUP BY camera_make, camera_model ORDER BY 3 DESC"
        ).fetchall()
        return [{"make": r[0] or "", "cameraModel": r[1],
                 "name": f"{r[0] or ''} {r[1]}".strip(), "photoCount": r[2]}
                for r in rows]

    @Slot(str, int, int, result="QVariant")
    def devicePhotos(self, model: str, offset: int = 0, limit: int = 500) -> list[dict]:
        where = "camera_model=?"
        return self._pack(self._photo_rows(where, (model,), limit, offset))

    @Slot(str, result=int)
    def deviceCount(self, model: str) -> int:
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND camera_model=?",
            (model,),
        ).fetchone()[0]

    @Slot(str, int, int, result="QVariant")
    def tagPhotos(self, tag: str, offset: int = 0, limit: int = 500) -> list[dict]:
        # 层级标签：精确 + 子孙前缀（旅行/...）
        where = ("EXISTS (SELECT 1 FROM photo_tags pt WHERE pt.photo_id = photos.id"
                 " AND (pt.tag=? OR pt.tag LIKE ? ESCAPE '\\'))")
        return self._pack(self._photo_rows(where, (tag, tag + "/%"), limit, offset))

    @Slot(str, result=int)
    def tagCount(self, tag: str) -> int:
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM photos p WHERE status != 'missing' AND"
            " EXISTS (SELECT 1 FROM photo_tags pt WHERE pt.photo_id = p.id"
            " AND (pt.tag=? OR pt.tag LIKE ? ESCAPE '\\'))",
            (tag, tag + "/%"),
        ).fetchone()[0]

    @Slot(result="QVariant")
    def tags(self) -> list[dict]:
        """标签列表：按标签聚合（扁平，向后兼容）。"""
        rows = self.db.conn.execute(
            "SELECT tag, COUNT(*) FROM photo_tags GROUP BY tag ORDER BY 2 DESC"
        ).fetchall()
        return [{"name": r[0], "photoCount": r[1]} for r in rows]

    @Slot(result="QVariant")
    def tagTree(self) -> list[dict]:
        """层级标签树（路径式 / 分隔），返回前序扁平列表，每项含 depth/photoCount。

        photoCount 为「该节点及其所有子孙」的去重照片数（一张照片同时拥有
        '旅行' 与 '旅行/北京' 两个标签时仅计一次）。UI 按 depth 缩进即为树。
        """
        conn = self.db.conn
        rows = conn.execute("SELECT photo_id, tag FROM photo_tags").fetchall()
        node_photos: dict[str, set] = {}
        children: dict[str, list] = {}
        roots: list[str] = []
        for pid, tag in rows:
            parts = tag.split("/")
            for i in range(1, len(parts) + 1):
                path = "/".join(parts[:i])
                node_photos.setdefault(path, set()).add(pid)
                if i == 1:
                    if path not in roots:
                        roots.append(path)
                else:
                    parent = "/".join(parts[:i - 1])
                    children.setdefault(parent, [])
                    if path not in children[parent]:
                        children[parent].append(path)

        def sk(path: str):
            return (-len(node_photos[path]), path)

        roots.sort(key=sk)
        for k in children:
            children[k].sort(key=sk)

        out: list[dict] = []

        def dfs(path: str, depth: int):
            out.append({
                "path": path,
                "name": path.rsplit("/", 1)[-1],
                "depth": depth,
                "photoCount": len(node_photos[path]),
            })
            for c in children.get(path, []):
                dfs(c, depth + 1)

        for r in roots:
            dfs(r, 0)
        return out

    def _rename_tag(self, src: str, dst: str) -> int:
        src, dst = (src or "").strip(), (dst or "").strip()
        if not src or not dst or src == dst:
            return 0
        conn = self.db.conn
        # 转义 LIKE 特殊字符，避免 src 含 %/_ 时前缀误匹配
        esc = src.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        try:
            conn.execute("BEGIN")
            # 1) 精确节点重命名
            cur = conn.execute(
                "INSERT INTO photo_tags(photo_id, tag)"
                " SELECT photo_id, ? FROM photo_tags WHERE tag=? "
                " ON CONFLICT(photo_id, tag) DO NOTHING", (dst, src))
            moved = cur.rowcount
            conn.execute("DELETE FROM photo_tags WHERE tag=?", (src,))
            # 2) 子孙：src/x -> dst/x（层级标签路径感知重命名）
            rows = conn.execute(
                "SELECT photo_id, tag FROM photo_tags WHERE tag LIKE ? ESCAPE '\\'",
                (esc + "/%",),
            ).fetchall()
            for pid, tag in rows:
                new_tag = dst + tag[len(src):]
                conn.execute(
                    "INSERT INTO photo_tags(photo_id, tag) VALUES (?,?) "
                    "ON CONFLICT(photo_id, tag) DO NOTHING", (pid, new_tag))
                conn.execute(
                    "DELETE FROM photo_tags WHERE photo_id=? AND tag=?", (pid, tag))
                moved += 1
            conn.commit()
            return moved
        except Exception:
            conn.rollback()
            return 0

    @Slot(str, str, result=int)
    def renameTag(self, old_tag: str, new_tag: str) -> int:
        """标签重命名（目标已存在时自动去重合并）。"""
        return self._rename_tag(old_tag, new_tag)

    @Slot(str, str, result=int)
    def mergeTags(self, src_tag: str, dst_tag: str) -> int:
        """标签合并：把 src 标签并入 dst（去重）。"""
        return self._rename_tag(src_tag, dst_tag)

    @Slot(result="QVariant")
    def events(self) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT id, title, start_at, end_at, photo_count, center_lat, center_lon"
            " FROM events ORDER BY start_at DESC"
        ).fetchall()
        return [
            {
                "id": r[0], "title": r[1] or "", "startAt": r[2] or "",
                "endAt": r[3] or "", "photoCount": r[4],
                "lat": r[5], "lon": r[6],
            }
            for r in rows
        ]

    @Slot(result="QVariant")
    def timeline(self) -> list[dict]:
        """按拍摄时间（年-月）聚合，返回 年→月 嵌套结构。"""
        rows = self.db.conn.execute(
            "SELECT substr(COALESCE(sort_key,''),1,7) AS ym, COUNT(*) FROM photos"
            " WHERE status != 'missing' AND archived = 0 AND taken_at IS NOT NULL AND taken_at != ''"
            " GROUP BY 1 ORDER BY 1 DESC"
        ).fetchall()
        years: dict[str, dict] = {}
        for ym, cnt in rows:
            year = ym[:4] if len(ym) >= 4 else ym
            month = ym
            y = years.setdefault(year, {"year": year, "photoCount": 0, "months": []})
            y["photoCount"] += cnt
            y["months"].append({"key": month, "label": month, "photoCount": cnt})
        return list(years.values())

    @Slot(str, result="QVariant")
    def timelineDays(self, ym: str) -> list[dict]:
        """某月（YYYY-MM）的天级计数。"""
        rows = self.db.conn.execute(
            "SELECT substr(COALESCE(sort_key,''),1,10) AS day, COUNT(*) FROM photos"
            " WHERE status != 'missing' AND archived = 0 AND taken_at IS NOT NULL AND taken_at != ''"
            " AND substr(COALESCE(sort_key,''),1,7)=?"
            " GROUP BY 1 ORDER BY 1 DESC", (ym,)
        ).fetchall()
        return [{"day": r[0], "label": r[0], "photoCount": r[1]} for r in rows]

    @Slot(str, int, int, result="QVariant")
    def dateMonthPhotos(self, ym: str, offset: int = 0, limit: int = 500) -> list[dict]:
        where = "substr(COALESCE(sort_key,''),1,7)=?"
        return self._pack(self._photo_rows(where, (ym,), limit, offset))

    @Slot(str, result=int)
    def dateMonthCount(self, ym: str) -> int:
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0 AND"
            " substr(COALESCE(sort_key,''),1,7)=?", (ym,)
        ).fetchone()[0]

    @Slot(str, int, int, result="QVariant")
    def datePhotos(self, day: str, offset: int = 0, limit: int = 500) -> list[dict]:
        where = "substr(COALESCE(sort_key,''),1,10)=?"
        return self._pack(self._photo_rows(where, (day,), limit, offset))

    @Slot(str, result=int)
    def dateCount(self, day: str) -> int:
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0 AND"
            " substr(COALESCE(sort_key,''),1,10)=?", (day,)
        ).fetchone()[0]

    @Slot(result="QVariant")
    def movedOutList(self) -> list[dict]:
        """已移出记录：按目标目录分组。"""
        rows = self.db.conn.execute(
            "SELECT dest_dir, COUNT(*), MAX(moved_at) FROM move_out_records"
            " GROUP BY dest_dir ORDER BY 3 DESC"
        ).fetchall()
        return [{"folder": r[0], "photoCount": r[1], "movedAt": r[2] or ""}
                for r in rows]

    @Slot(str, result=str)
    def reimportMovedOut(self, folder: str) -> str:
        """重新扫描指定目录恢复已移出照片（后台线程）。"""
        from photo_manager.core.pipeline import IngestPipeline

        with self._busy_lock:
            if self._busy > 0:
                self._finish("导入已取消：有任务正在运行，请稍候")
                return ""
            self._busy = 1
        self.message.emit(_tr("正在扫描 {p1} …").format(p1=folder))

        def prog(done, total, path=""):
            self.taskProgress.emit(done or 0, total or 0, "恢复移出照片")

        def worker():
            try:
                stats = IngestPipeline(self.db, Path(self.db.path).parent).ingest(
                    folder, progress_cb=prog)
                # 0.6.10：后台 worker 独立连接（不与 UI 共享）
                import sqlite3 as _sq

                wconn = _sq.connect(self.db.path, timeout=10)
                try:
                    wconn.execute(
                        "DELETE FROM move_out_records WHERE dest_dir=?", (folder,))
                    wconn.commit()
                finally:
                    wconn.close()
                self._finish(
                    _tr("已重新导入 {p1} 张（失败 {p2}）").format(
                        p1=stats.get('indexed', 0), p2=stats.get('failed', 0)))
                self.photosChanged.emit()
            except Exception as e:
                log.exception("恢复移出照片失败")
                self._finish(_tr("恢复失败：{p1}").format(p1=e))
            finally:
                self._release_busy()

        threading.Thread(target=worker, daemon=True).start()
        return ""

    def _pack(self, rows) -> list[dict]:
        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "thumb": self._thumb_url(r[1]),
                "name": r[2],
                "takenAt": (r[3] or "")[:16].replace("T", " "),
                "faceCount": r[4],
                "hasText": bool(r[5]),
                "cameraModel": r[6] or "",
                "path": r[7],
                "width": r[8] or 0,
                "height": r[9] or 0,
                "rating": r[10] or 0,
                "flag": r[11] or "",
                "colorLabel": r[12] or "",
                # 0.5.44 视频：mediaType/duration。仅 _photo_rows/photos() 提供 15 列，
                # 其它 13 列直接查询经长度 guard 安全降级为 photo/None。
                "mediaType": r[13] if len(r) > 13 else "photo",
                "duration": r[14] if len(r) > 14 else None,
                # 0.5.64 损坏文件标记（仅 _photo_rows 的 16 列查询带出）
                "decodeError": bool(r[15]) if len(r) > 15 else False,
            })
        return out

    def _resolve(self, p: str | None) -> Path | None:
        """解析照片/缩略图路径：相对路径依次尝试 db 目录、项目根。"""
        if not p:
            return None
        cand = Path(p)
        if cand.is_absolute():
            return cand if cand.exists() else None
        base = Path(self.db.path).resolve().parent
        for rel in (base / p, base.parent / p, base.parent.parent / p):
            if rel.exists():
                return rel
        return None

    def _migrate_thumb_paths(self) -> None:
        """0.5.51 一次性迁移：断链的绝对缩略图路径 → 相对路径。

        0.5.50 及以前 thumbnail_path 存**绝对路径**（指向当时的程序目录）。
        程序目录一移动/改名（便携软件常态、打包换版），全部断链 → 缩略图
        空白（用户实测"同文件夹跳转中间栏空白"即此现象）。本迁移把「绝对
        路径已不存在、但按 thumbs 尾缀能在当前数据目录找到」的行改写为相对
        路径；仍有效的绝对路径不动；找不到的保持原样（重新生成时覆盖）。
        """
        try:
            rows = self.db.conn.execute(
                "SELECT id, thumbnail_path FROM photos"
                " WHERE thumbnail_path IS NOT NULL AND thumbnail_path != ''"
                " AND thumbnail_path NOT LIKE 'thumbs/%'").fetchall()
            if not rows:
                return
            base = Path(self.db.path).resolve().parent
            fixes = []
            for pid, tp in rows:
                t = str(tp)
                if Path(t).exists():
                    continue
                parts = Path(t).as_posix().split("/thumbs/")
                if len(parts) == 2 and (base / "thumbs" / parts[-1]).exists():
                    fixes.append((f"thumbs/{parts[-1]}", pid))
            if fixes:
                self.db.conn.executemany(
                    "UPDATE photos SET thumbnail_path=? WHERE id=?", fixes)
                self.db.conn.commit()
                log.info("缩略图路径相对化迁移：%d 行（共扫描 %d）",
                         len(fixes), len(rows))
        except Exception:
            log.exception("缩略图路径迁移失败（不影响使用，仅缩略图可能空白）")

    def _thumb_url(self, thumb_path: str | None) -> str:
        p = self._resolve(thumb_path)
        if p is None:
            return ""
        # QUrl 负责 URL 编码（中文/空格/#/% 等字符），QML Image 才能正确加载
        from PySide6.QtCore import QUrl

        return QUrl.fromLocalFile(str(p)).toString()

    # ---------- 文件系统辅助（自绘文件夹/文件选择器） ----------
    @Slot(result=str)
    def fsHome(self) -> str:
        return os.path.expanduser("~")

    @Slot(int, result=bool)
    def openFolder(self, photo_id: int) -> bool:
        """在系统文件管理器中打开照片所在文件夹（Windows 用资源管理器）。"""
        d = self.photoDetail(photo_id)
        if not d:
            return False
        folder = d.get("folder") or ""
        if not folder or not os.path.isdir(folder):
            return False
        import subprocess
        if sys.platform == "win32":
            try:
                os.startfile(folder)  # type: ignore[attr-defined]
            except OSError:
                return False
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
        return True

    @Slot(str, result=bool)
    def openExternal(self, path: str) -> bool:
        """用系统默认程序打开文件（0.5.44 视频：交给默认播放器播放）。
        与 openFolder 同款跨平台外开（startfile/open/xdg-open）；仅启动，不读写内容。"""
        if not path:
            return False
        target = path
        fp = self._resolve(path)
        if fp is not None:
            target = str(fp)
        if not os.path.exists(target):
            return False
        import subprocess
        try:
            if sys.platform == "win32":
                os.startfile(target)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
        except Exception:
            return False
        return True

    @Slot(result=str)
    def fsLastRoot(self) -> str:
        """最近一次扫描的根路径（自绘选择器的初始位置）。
        跳过已不存在/不可访问的目录（如被移走的盘、手输错的库根）。"""
        rows = self.db.conn.execute(
            "SELECT path FROM scan_roots ORDER BY last_scan_at DESC"
        ).fetchall()
        for (p,) in rows:
            if p and os.path.isdir(p):
                return p
        return ""

    @Slot(result="QVariant")
    def fsRoots(self) -> list[dict]:
        """根级别列表：Windows 为盘符，Linux 为 /。"""
        if os.name == "nt":
            import string

            return [
                {"name": f"{c}:\\", "path": f"{c}:\\", "isDir": True}
                for c in string.ascii_uppercase
                if os.path.exists(f"{c}:\\")
            ]
        return [{"name": "/", "path": "/", "isDir": True}]

    @Slot(str, result="QVariant")
    def searchFolders(self, name: str) -> list[dict]:
        """按名称搜索库内已收录的文件夹（0.6.6：目录选择弹窗的搜索框）。

        范围 = photos.folder_path DISTINCT（用户实际有照片的目录），
        大小写不敏感子串匹配，按路径排序，最多 60 条。
        返回 [{name(目录名), path(完整路径), photoCount}]——name/path 字段
        与 fsChildren 的行结构一致，目录选择弹窗的列表委托可直接复用。
        """
        q = (name or "").strip()
        if not q:
            return []
        esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = self.db.conn.execute(
            "SELECT folder_path, COUNT(*) AS c FROM photos"
            " WHERE folder_path LIKE ? ESCAPE '\\'"
            " GROUP BY folder_path ORDER BY folder_path LIMIT 60",
            (f"%{esc}%",)).fetchall()
        from pathlib import Path as _P

        out = []
        for fp, cnt in rows:
            norm = (fp or "").replace("\\", "/")
            out.append({"name": _P(norm).name or norm,
                        "path": fp, "photoCount": cnt})
        return out

    @Slot(str, result="QVariant")
    def fsChildren(self, path: str) -> list[dict]:
        """列出目录内容（目录在前、名称排序）；空/根路径返回盘符或 /。"""
        if not path:
            return self.fsRoots()
        try:
            with os.scandir(path) as it:
                out = []
                for e in it:
                    try:
                        if e.is_dir() or e.is_file():
                            out.append(
                                {"name": e.name, "path": e.path, "isDir": e.is_dir()}
                            )
                    except OSError:
                        pass
        except OSError:
            return []
        out.sort(key=lambda d: (not d["isDir"], d["name"].lower()))
        return out

    # ---------- 系统浏览器式文件夹树（侧边栏"全部照片"下拉） ----------
    def _indexedDirs(self) -> dict[str, str]:
        """绝对目录路径(小写,正斜杠) -> 该目录在库中登记的原始 folder_path。

        供侧边栏文件树标记"已添加"文件夹并统计照片数。惰性缓存。
        """
        if self._dir_cache is not None:
            return self._dir_cache
        conn = self.db.conn
        raw: dict[str, str] = dict()
        for fp, in conn.execute(
            "SELECT DISTINCT folder_path FROM photos"
            " WHERE status != 'missing' AND folder_path IS NOT NULL AND folder_path != ''"
        ).fetchall():
            absd = self._resolveDir(fp)
            if absd:
                raw.setdefault(absd, fp)
        # 把库内子目录的绝对父目录路径也纳入（含祖先目录，逐级向上补全）
        keys = list(raw.keys())
        for k in keys:
            parts = k.split("/")
            for i in range(1, len(parts)):
                raw.setdefault("/".join(parts[: i + 1]), raw[k])
        self._dir_cache = raw
        return raw

    def _resolveDir(self, p: str | None) -> str | None:
        """把路径解析为可比较的绝对目录（小写、正斜杠、去尾斜杠）。

        0.6.10：POSIX 根路径 "/" 特殊保留——原 rstrip("/") 会把 "/" 剥成
        空串，_has_photos("") 恒 False，Linux 上文件夹树"仅已添加"模式
        整棵为空（Windows 根是盘符 "D:" 不受影响，故仅麒麟实测暴露）。"""
        if not p:
            return None
        d = os.path.abspath(p).replace("\\", "/")
        if len(d) > 1 and d.endswith("/"):
            d = d.rstrip("/")
        return d.lower()

    @staticmethod
    def _dir_prefix(ad: str | None) -> str:
        """目录前缀：POSIX 根 "/" 的前缀是 ""（而非 "//"，见 _resolveDir）。"""
        if not ad:
            return ""
        return "" if ad == "/" else ad + "/"

    def _has_photos(self, abs_dir: str | None) -> bool:
        """给定绝对目录（来自文件系统），判断其内（含子树）是否有已索引照片。"""
        if not abs_dir:
            return False
        ad = abs_dir
        prefix = self._dir_prefix(ad)
        for k in self._indexedDirs():
            if k == ad or k.startswith(prefix):
                return True
        return False

    def _directIndexedDirs(self) -> set[str]:
        """直接含已索引照片的目录绝对路径集合（不含祖先目录）。"""
        if self._direct_cache is not None:
            return self._direct_cache
        direct: set[str] = set()
        conn = self.db.conn
        for (fp,) in conn.execute(
            "SELECT DISTINCT folder_path FROM photos"
            " WHERE status != 'missing'"
            " AND folder_path IS NOT NULL AND folder_path != ''"
        ).fetchall():
            ad = self._resolveDir(fp)
            if ad:
                direct.add(ad)
        self._direct_cache = direct
        return direct

    def _scanRootDirs(self) -> set[str]:
        """已入库的根目录（scan_roots）绝对路径集合。"""
        conn = self.db.conn
        out: set[str] = set()
        for (p,) in conn.execute("SELECT path FROM scan_roots").fetchall():
            ad = self._resolveDir(p)
            if ad:
                out.add(ad)
        return out

    def _treeState(self, abs_dir: str | None) -> int:
        """三态复选框状态：2=该目录自身已入库（直接含照片或为扫描根），
        1=仅子目录中有已入库照片（部分），0=未添加。"""
        if not abs_dir:
            return 0
        if abs_dir in self._directIndexedDirs() or abs_dir in self._scanRootDirs():
            return 2
        if self._has_photos(abs_dir):
            return 1
        return 0

    @Slot(str, result="QVariant")
    def dirChildren(self, path: str = "") -> list[dict]:
        """系统浏览器式文件夹树的一层子目录：附加 added/photoCount/hasSub/state 标记。

        仅返回子目录（不含文件）；
        added=true 表示该目录内或其子树中含已索引照片；
        state 为三态复选框值：2=该目录自身已入库，1=部分子目录已入库，0=未添加；
        hasSub=true 表示该目录下有子目录（系统浏览器用展开箭头）；
        hasAddedSub=true 表示该目录的子级中含已添加内容（仅已添加模式的展开依据）。
        """
        kids = self.fsChildren(path)
        indexed = self._indexedDirs()
        out = []
        for k in kids:
            if not k["isDir"]:
                continue
            ad = self._resolveDir(k["path"]) or ""
            added = self._has_photos(ad)
            cnt = self._dirCountAbs(ad) if added else 0
            state = self._treeState(ad)
            has_added_sub = any(
                fk != ad and fk.startswith(self._dir_prefix(ad))
                for fk in indexed)
            out.append({
                "name": k["name"], "path": k["path"], "isDir": True,
                "added": added, "photoCount": cnt,
                "state": state,
                "hasSub": True, "hasAddedSub": has_added_sub,
            })
        return out

    def _dirCountAbs(self, abs_dir: str | None) -> int:
        """统计绝对目录（或其子树）下的已索引照片数。"""
        if not abs_dir:
            return 0
        idx = self._indexedDirs()
        prefix = self._dir_prefix(abs_dir)
        stored = {fp for k, fp in idx.items()
                  if k == abs_dir or k.startswith(prefix)}
        if not stored:
            return 0
        q = ",".join("?" for _ in stored)
        return self.db.conn.execute(
            f"SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0 AND folder_path IN ({q})",
            tuple(sorted(stored)),
        ).fetchone()[0]

    @Slot(str, result=int)
    def dirCount(self, path: str) -> int:
        """某绝对目录（含子树）下的已索引照片数。"""
        return self._dirCountAbs(self._resolveDir(path))

    @Slot(str, int, int, result="QVariant")
    def dirPhotos(self, path: str, offset: int = 0, limit: int = 500) -> list[dict]:
        """加载某绝对目录（含子树）下的已索引照片。"""
        ad = self._resolveDir(path)
        if not ad:
            return []
        idx = self._indexedDirs()
        prefix = self._dir_prefix(ad)
        stored = sorted(
            {fp for k, fp in idx.items() if k == ad or k.startswith(prefix)}
        )
        if not stored:
            return []
        where = "folder_path IN ({})".format(",".join("?" for _ in stored))
        rows = self.db.conn.execute(
            " SELECT id, thumbnail_path, file_name, taken_at, face_count, has_text,"
            " camera_model, file_path, width, height, rating, flag, color_label,"
            " media_type, duration FROM photos"
            f" WHERE status != 'missing' AND archived = 0 AND {where}"
            " ORDER BY sort_key DESC, id DESC LIMIT ? OFFSET ?",
            (*sorted(stored), limit, offset),
        ).fetchall()
        return self._pack(rows)

    @Slot(str, result=str)
    def fsParent(self, path: str) -> str:
        """返回父目录；已是根时返回空串（QML 显示根列表）。"""
        p = (path or "").rstrip("/\\")
        if not p:
            return ""
        parent = os.path.dirname(p)
        if parent in ("", p):
            if os.name == "nt":
                drive = os.path.splitdrive(p)[0]
                return (drive + "\\") if drive else ""
            return "/"
        return parent

    # ---------- 搜索 ----------
    @Slot(str, int, int, result="QVariant")
    def searchPhotos(self, q: str, offset: int = 0, limit: int = 500) -> list[dict]:
        hits = self.search.query(q, limit=limit, offset=offset)
        return self._pack(
            [
                (h["id"], h["thumbnail_path"], h["file_name"], h["taken_at"],
                 h["face_count"], h["has_text"], h["camera_model"], h["file_path"],
                 h["width"], h["height"], h["rating"], h["flag"], h["color_label"])
                for h in hits
            ]
        )

    @Slot(str, result="QVariant")
    def suggest(self, q: str) -> list[str]:
        return self.search.suggest(q)

    # ---------- 详情 ----------
    @Slot(int, result="QVariant")
    def videoFrames(self, photo_id: int) -> list[dict]:
        """视频关键帧 URL 列表（0.5.51，供信息面板帧带展示）。

        路径按 DB 目录解析（库内存相对路径）；文件缺失的帧跳过。
        """
        from PySide6.QtCore import QUrl

        from photo_manager.core.paths import resolve_data_path

        out = []
        for (p,) in self.db.conn.execute(
                "SELECT path FROM video_frames WHERE photo_id=? ORDER BY idx",
                (photo_id,)).fetchall():
            ap = resolve_data_path(self.db.path, p)
            if os.path.exists(ap):
                out.append({"url": QUrl.fromLocalFile(ap).toString()})
        return out

    @Slot(int, result=str)
    def photoViewUrl(self, photo_id: int) -> str:
        """大图查看 URL（0.5.51：修复 RAW/HEIC/AVIF 等大图空白）。

        Qt 图像插件只解 jpg/png/webp/tiff 等；相机 RAW（44 种）、HEIC、
        AVIF、FITS/HDR/EXR 等 Qt QImage 一律返回 null——此前查看器直接
        加载原文件 → 空白（缩略图却正常，因为缩略图走 extractor）。
        本槽对这些格式按需生成解码预览 JPEG（data/previews/，内容哈希
        命名=源文件变化自动失效），返回预览 URL；解不了返回 ""（QML
        显示占位，不崩）。
        """
        import hashlib

        from PySide6.QtCore import QUrl

        r = self.db.conn.execute(
            "SELECT file_path, ext FROM photos WHERE id=?", (photo_id,)).fetchone()
        if not r:
            return ""
        fp = self._resolve(r[0])
        if fp is None:
            return ""
        ext = (r[1] or Path(r[0]).suffix).lower()
        if ext in _QT_NATIVE_EXTS:
            return QUrl.fromLocalFile(str(fp)).toString()
        # 解码预览（按需生成 + 缓存）
        h = hashlib.sha1(str(r[0]).encode("utf-8")).hexdigest()
        prev_dir = Path(self.db.path).resolve().parent / "previews" / h[:2]
        prev = prev_dir / (h[2:16] + ".jpg")
        if not prev.exists():
            from photo_manager.core import extractor

            prev_dir.mkdir(parents=True, exist_ok=True)
            tmp = prev.with_suffix(".tmp")
            try:
                pr = extractor.make_preview_ex(str(fp), tmp)
                if pr is None:
                    # 完全无法解码 → 标记损坏（预览占位，不崩）
                    self._set_decode_error(photo_id, True)
                    return ""
                state = pr[2]
                # 0.5.64：全图解码失败的兜底预览 = 文件很可能损坏；
                # "ok"/"unverified"（内嵌快速路径）不作为损坏证据
                self._set_decode_error(photo_id, state == "fallback")
                tmp.replace(prev)
            except Exception:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
                return ""
        return QUrl.fromLocalFile(str(prev)).toString()

    def _set_decode_error(self, photo_id: int, broken: bool) -> None:
        """写/清 photos.decode_error（0.5.64 损坏文件标记）。仅在变化时写。"""
        try:
            self.db.conn.execute(
                "UPDATE photos SET decode_error=? WHERE id=? AND decode_error != ?",
                (1 if broken else 0, photo_id, 1 if broken else 0))
            self.db.conn.commit()
        except Exception:
            log.debug("decode_error 写库失败 id=%s", photo_id, exc_info=True)

    @Slot(int, result="QVariant")
    def photoDetail(self, photo_id: int) -> dict:
        r = self.db.conn.execute(
            "SELECT file_name, file_path, taken_at, camera_make, camera_model, lens_model,"
            " exposure, f_number, iso, focal_length, gps_lat, gps_lon, gps_alt,"
            " width, height, face_count, ocr_text, file_size, folder_path, error, thumbnail_path,"
            " rating, flag, archived, color_label, media_type, duration, video_codec, decode_error"
            " FROM photos WHERE id=?", (photo_id,),
        ).fetchone()
        if not r:
            return {}
        ocr = self.db.conn.execute(
            "SELECT text, conf FROM ocr_texts WHERE photo_id=? ORDER BY conf DESC", (photo_id,)
        ).fetchall()
        from PySide6.QtCore import QUrl

        fp = self._resolve(r[1])
        full = QUrl.fromLocalFile(str(fp)).toString() if fp else ""
        # 0.5.64：folder_path 库内统一正斜杠（见 pipeline 落库 replace("\\","/")），
        # 这里必须同样归一——否则「同文件夹」跳转用反斜杠匹配 folder_path 恒 0 条
        parent_dir = str(fp.parent).replace("\\", "/") if fp else (r[18] or "")
        return {
            "id": photo_id, "name": r[0], "path": r[1], "takenAt": (r[2] or "")[:16].replace("T", " "),
            "make": r[3] or "", "model": r[4] or "", "lens": r[5] or "",
            "exposure": r[6] or "", "fNumber": r[7], "iso": r[8],
            "focal": r[9], "lat": r[10], "lon": r[11], "alt": r[12],
            "width": r[13] or 0, "height": r[14] or 0, "faces": r[15] or 0,
            "ocr": "；".join(f"{t[0]}（{t[1]:.2f}）" for t in ocr) or "",
            "sizeKB": round((r[17] or 0) / 1024), "folder": parent_dir,
            "error": r[19] or "",
            "thumb": self._thumb_url(r[20]),
            "fullUrl": full,
            "rating": r[21] or 0,
            "flag": r[22] or "",
            "archived": bool(r[23] or 0),
            "colorLabel": r[24] or "",
            "mediaType": r[25] or "photo",
            "duration": r[26],
            "videoCodec": r[27] or "",
            "decodeError": bool(r[28] or 0),
        }

    # ---------- 导出（仅复制，无删除；后台执行避免大文件阻塞界面） ----------
    @Slot("QVariant", str, result=int)
    def exportPhotos(self, ids, dest_dir: str) -> int:
        from PySide6.QtQml import QJSValue

        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        with self._busy_lock:
            if self._busy > 0:
                self._finish("导出已取消：有任务正在运行，请稍候")
                return 0
            self._busy = 1
        self.message.emit(_tr("正在导出…"))
        threading.Thread(
            target=self._export_worker, args=(list(ids), dest_dir), daemon=True
        ).start()
        return len(ids)

    def _export_worker(self, ids, dest_dir: str) -> None:
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        # 0.6.10：后台 worker 改独立连接，不再与 UI 共享（pysqlite 语句缓存
        # 跨线程竞态隐患；主键点查本身量小，属稳妥性修正）
        import sqlite3

        conn = sqlite3.connect(self.db.path, timeout=10)
        n = 0
        try:
            for pid in ids:
                r = conn.execute(
                    "SELECT file_path, file_name FROM photos WHERE id=?", (pid,)
                ).fetchone()
                if not r:
                    continue
                src = Path(r[0])
                target = dest / r[1]
                if target.exists():
                    target = dest / f"{target.stem}_{pid}{target.suffix}"
                try:
                    shutil.copy2(src, target)
                    n += 1
                    self._record_export(pid, target.name, dest,
                                        "original", "original", conn)
                except OSError as e:
                    log.warning("导出失败 %s: %s", src, e)
        finally:
            conn.close()
            self._release_busy()
        self._finish(_tr("已导出 {p1} 张到 {p2}").format(p1=n, p2=dest))

    def _record_export(self, photo_id: int, file_name: str, dest_dir: Path,
                       fmt: str, res: str, conn=None) -> None:
        """写入导出历史（0.5.39「已导出」页数据源；记录失败不影响导出）。

        0.6.10：后台 worker 可传入自己的独立连接（避免与 UI 共享连接）。"""
        try:
            c = conn or self.db.conn
            c.execute(
                "INSERT INTO export_records(photo_id, file_name, dest_dir, fmt, res)"
                " VALUES (?,?,?,?,?)",
                (photo_id, file_name, str(dest_dir), fmt, res),
            )
            c.commit()
        except Exception:  # noqa: BLE001
            log.exception("导出历史记录失败")

    # 导出格式 / 分辨率白名单（0.5.38）
    EXPORT_FORMATS: dict[str, tuple[str, str]] = {
        "jpg": ("JPEG", ".jpg"),
        "png": ("PNG", ".png"),
        "webp": ("WEBP", ".webp"),
        "tiff": ("TIFF", ".tiff"),
    }
    EXPORT_RES: dict[str, int] = {"original": 0, "s1080": 1080, "s800": 800, "s640": 640}

    @Slot("QVariant", str, str, str, result=int)
    def exportProcessed(self, ids, dest_dir: str, fmt: str, res_key: str) -> int:
        """按所选格式/分辨率导出（0.5.38）。

        fmt: original=保持原格式（重设分辨率时按原格式重编码），否则 jpg/png/webp/tiff。
        res_key: original=原始；s1080/s800/s640=短边目标，只缩小不放大。
        """
        from PySide6.QtQml import QJSValue

        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        if fmt not in ("original",) and fmt not in self.EXPORT_FORMATS:
            fmt = "original"
        if res_key not in self.EXPORT_RES:
            res_key = "original"
        ids = [int(i) for i in (ids or [])]
        if not ids:
            self._finish("导出未开始：未选择照片")
            return 0
        with self._busy_lock:
            if self._busy > 0:
                self._finish("导出已取消：有任务正在运行，请稍候")
                return 0
            self._busy = 1
        self.message.emit(_tr("正在导出照片…"))
        threading.Thread(
            target=self._export_processed_worker,
            args=(ids, dest_dir, fmt, self.EXPORT_RES[res_key]),
            daemon=True,
        ).start()
        return len(ids)

    def _export_processed_worker(self, ids, dest_dir: str,
                                 fmt: str, short_edge: int) -> None:
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        ok = fail = 0
        self._export_fail_names = []
        try:
            for pid in ids:
                r = self.db.conn.execute(
                    "SELECT file_path, file_name FROM photos WHERE id=?", (pid,)
                ).fetchone()
                if not r:
                    fail += 1
                    continue
                src = Path(r[0])
                try:
                    need_recode = fmt != "original" or short_edge > 0
                    if not need_recode:
                        target = dest / r[1]
                        if target.exists():
                            target = dest / f"{target.stem}_{pid}{target.suffix}"
                        shutil.copy2(src, target)
                        ok += 1
                        continue
                    from PIL import Image, ImageOps  # noqa: PLC0415

                    # 0.5.67：RAW（CR2/NEF/ARW 等）Pillow 打不开 → 用 rawpy 解码。
                    # 此前 RAW 走重编码路径必失败，"只能导出原片"（用户反馈）。
                    from photo_manager.core.extractor import _RAW_EXTS as _PM_RAW_EXTS

                    if src.suffix.lower() in _PM_RAW_EXTS:
                        import rawpy  # noqa: PLC0415

                        with rawpy.imread(str(src)) as raw:
                            rgb = raw.postprocess(use_camera_wb=True)
                        im = Image.fromarray(rgb)
                        w, h = im.size
                    else:
                        with Image.open(src) as opened:
                            opened.load()
                            # 转码时统一 bake 方向：EXIF 旋转进像素，显示不再依赖阅读器
                            im = ImageOps.exif_transpose(opened)
                        w, h = im.size
                    short = min(w, h)
                    if short_edge > 0 and short > short_edge:
                        scale = short_edge / short
                        im = im.resize(
                            (max(1, round(w * scale)), max(1, round(h * scale))),
                            Image.LANCZOS,
                        )
                    if fmt == "original":
                        ext = src.suffix.lower().lstrip(".")
                        pair = {"jpg": ("JPEG", ".jpg"), "jpeg": ("JPEG", ".jpg"),
                                "png": ("PNG", ".png"), "webp": ("WEBP", ".webp"),
                                "tif": ("TIFF", ".tiff"), "tiff": ("TIFF", ".tif")}.get(ext)
                        if pair is None:  # 冷门原格式：按原文件直接复制（不缩放降级）
                            target = dest / f"{src.stem}_{pid}{src.suffix}"
                            shutil.copy2(src, target)
                            ok += 1
                            self._record_export(pid, target.name, dest,
                                                "original",
                                                "original" if short_edge == 0
                                                else f"s{short_edge}")
                            continue
                        pil_fmt, ext2 = pair
                    else:
                        pil_fmt, ext2 = self.EXPORT_FORMATS[fmt]
                    target = dest / f"{src.stem}{ext2}"
                    if target.exists():
                        target = dest / f"{src.stem}_{pid}{ext2}"
                    kw: dict = {}
                    if pil_fmt in ("JPEG", "WEBP"):
                        kw["quality"] = 92
                    if pil_fmt != "PNG":
                        exif = im.info.get("exif")
                        if exif:
                            kw["exif"] = exif
                    icc = im.info.get("icc_profile")
                    if icc:
                        kw["icc_profile"] = icc
                    im.save(target, pil_fmt, **kw)
                    ok += 1
                    self._record_export(pid, target.name, dest,
                                        fmt, "original" if short_edge == 0
                                        else f"s{short_edge}")
                except Exception as e:  # noqa: BLE001
                    fail += 1
                    self._export_fail_names.append(r[1])
                    log.warning("导出失败 %s: %s", src, e)
        finally:
            self._release_busy()
        msg = _tr("已导出 {p1} 张到 {p2}").format(p1=ok, p2=dest)
        if fmt != "original" or short_edge > 0:
            fmt_txt = "原格式" if fmt == "original" else fmt.upper()
            res_txt = "原始分辨率" if short_edge == 0 else _tr("短边 {p1}px").format(p1=short_edge)
            msg += f"（{fmt_txt} · {res_txt}）"
        if fail:
            msg += _tr(" · 失败 {p1} 张").format(p1=fail)
            # 0.5.67：列出让失败的具体文件（如损坏的 RAW——文件本身问题，
            # 非导出缺陷；用户此前 3 张失败即 SampleRAW 下载不完整的坏文件）
            if fail <= 6:
                msg += "：" + "、".join(self._export_fail_names[-fail:])
            else:
                msg += "：" + "、".join(self._export_fail_names[:4]) + _tr(" 等")
        self._finish(msg)

    # ---------- 预删除（移出管理）：移动到指定文件夹并从索引清除 ----------
    @Slot("QVariant", str, result=int)
    def moveOut(self, ids, dest_dir: str) -> int:
        """把选中照片移到指定文件夹（不删除任何文件），移出后从数据库/索引/归类清除。
        移动前检查目标所在磁盘空间，不足则拒绝并提示。"""
        from PySide6.QtQml import QJSValue

        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        with self._busy_lock:
            if self._busy > 0:
                self._finish("移出已取消：有任务正在运行，请稍候")
                return 0
            self._busy = 1
        self.message.emit(_tr("正在移出照片…"))
        threading.Thread(
            target=self._move_out_worker, args=(list(ids), dest_dir), daemon=True
        ).start()
        return len(ids)

    @staticmethod
    def _dest_free(dest: Path) -> int:
        """目标所在磁盘可用字节数；不可用返回 -1。"""
        p = dest
        while p and not p.exists():
            p = p.parent
        if not p:
            return -1
        try:
            return shutil.disk_usage(p).free
        except OSError:
            return -1

    def _move_out_worker(self, ids, dest_dir: str) -> None:
        dest = Path(dest_dir)
        # 0.6.10：后台 worker 改独立连接（与 _export_worker 同理由）
        import sqlite3

        conn = sqlite3.connect(self.db.path, timeout=10)
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._finish(_tr("移出失败：目标文件夹不可用（{p1}）").format(p1=e))
            self._release_busy()
            conn.close()
            return

        try:
            self._move_out_worker_inner(ids, dest, conn)
        except Exception:
            log.exception("移出照片失败")
            self._finish(_tr("移出失败：{p1}").format(p1=sys.exc_info()[1]))
            self._release_busy()
        finally:
            conn.close()

    def _move_out_worker_inner(self, ids, dest: Path, conn) -> None:

        rows = []
        for pid in ids:
            r = conn.execute(
                "SELECT file_path, file_name, thumbnail_path FROM photos WHERE id=?",
                (pid,),
            ).fetchone()
            if r:
                rows.append((pid, r[0], r[1], r[2]))
        total = len(rows)
        if not total:
            self._finish("移出失败：没有找到选中的照片记录")
            self._release_busy()
            return

        # 空间检查：目标磁盘可用空间 >= 所有现存源文件总大小
        need = 0
        for _, path, _, _ in rows:
            try:
                need += os.path.getsize(path)
            except OSError:
                pass
        free = self._dest_free(dest)
        if free >= 0 and free < need:
            self._finish(
                _tr("移出已取消：目标空间不足（需要 {p1} MB，可用 {p2} MB）。"
                    "请清理空间或选择其他文件夹后重试。").format(
                        p1=format(need / 1024 ** 2, ".0f"),
                        p2=format(free / 1024 ** 2, ".0f"))
            )
            self._release_busy()
            return

        moved = failed = cleared = 0
        for i, (pid, path, name, thumb) in enumerate(rows, 1):
            src = Path(path)
            if not src.exists():
                # 源文件已在系统外删除：无法移动，但仍从管理索引中清除
                conn.execute("DELETE FROM photos WHERE id=?", (pid,))
                if thumb:
                    try:
                        os.unlink(thumb)
                    except OSError:
                        pass
                cleared += 1
                log.warning("移出：源文件已不存在，仅清除索引 %s", src)
                if i % 10 == 0 or i == total:
                    self.taskProgress.emit(i, total, "移出照片")
                continue
            if dest.resolve() == src.parent.resolve():
                failed += 1
                self._finish(_tr("移出失败：{p1} 已在目标文件夹中").format(p1=name))
                continue
            target = dest / name
            if target.exists():
                target = dest / f"{Path(name).stem}_{pid}{Path(name).suffix}"
            try:
                shutil.move(str(src), str(target))
            except OSError as e:
                failed += 1
                log.warning("移出失败 %s: %s", src, e)
                continue
            # 从库中清除（faces/ocr_texts/photo_tags/event_photos 级联删除，FTS 触发器同步）
            conn.execute("DELETE FROM photos WHERE id=?", (pid,))
            # 记录"已移出"供回收站一键恢复（同一事务，失败回滚不产生脏记录）
            conn.execute(
                "INSERT INTO move_out_records(dest_dir, file_name) VALUES (?,?)",
                (str(dest), target.name))
            if thumb:
                try:
                    os.unlink(thumb)
                except OSError:
                    pass
            moved += 1
            if i % 10 == 0 or i == total:
                self.taskProgress.emit(i, total, "移出照片")
        conn.execute(
            "UPDATE events SET photo_count = (SELECT COUNT(*) FROM event_photos"
            " WHERE event_id = events.id)"
        )
        conn.commit()
        self._release_busy()
        extra = _tr("，另清除 {p1} 条源文件已丢失的记录").format(p1=cleared) if cleared else ""
        if failed:
            self._finish(_tr("移出完成：{p1} 张已移到 {p2} 并从索引清除，").format(p1=moved, p2=dest)
                         + _tr("{p1} 张失败{p2}").format(p1=failed, p2=extra))
        else:
            self._finish(_tr("已移出 {p1} 张到 {p2}，并从索引、搜索与归类中清除{p3}").format(p1=moved, p2=dest, p3=extra))
        self.photosChanged.emit()

    # ---------- 重建索引：检查系统外删除，排除失效记录避免出错 ----------
    @Slot(result=str)
    def reindexCheck(self) -> str:
        """检查索引中文件是否已在系统外被删除：标记 missing 并从视图/搜索/归类排除。"""

        def task(prog):
            conn = self.db.conn
            rows = conn.execute(
                "SELECT id, file_path FROM photos"
            ).fetchall()
            total = len(rows)
            missing = 0
            for i, (pid, path) in enumerate(rows, 1):
                if not os.path.exists(path):
                    missing += 1
                    conn.execute(
                        "UPDATE photos SET status='missing', error=NULL WHERE id=?",
                        (pid,),
                    )
                    conn.execute("DELETE FROM photos_fts WHERE rowid=?", (pid,))
                    conn.execute("DELETE FROM ocr_fts WHERE rowid=?", (pid,))
                    # 注意：不删除缩略图。文件可能只是临时离线（外接盘未连接），
                    # 保留缩略图便于恢复后（扫描器自动解除 missing）立即使用。
                if i % 200 == 0:
                    conn.commit()
                    prog(i, total)
            conn.commit()
            return {"checked": total, "missing": missing}

        self._spawn("reindex", "索引检查", self._run_with_progress(task, "索引检查"))
        return ""

    # ---------- 库完整性校验（只读）：缺失 / 被改动 / 缩略图丢失 / 分析失败 ----------
    @Slot(result=str)
    @Slot(str, result=str)
    def integrityCheck(self, folder: str = "") -> str:
        """后台**只读**校验：比对索引与磁盘，完成后 emit integrityFinished(JSON 摘要)。

        校验本身不改任何数据；发现的问题由用户在报告中决定如何处理。
        0.5.67：folder 非空时只校验该文件夹（含子文件夹）——范围选择。
        """

        def task(prog):
            from photo_manager.core.integrity import check_integrity
            rep = check_integrity(self.db, prog, folder=folder)
            self._integrity = rep
            c = rep["counts"]
            self.integrityFinished.emit(json.dumps(
                {"total": rep["total"], "ok": rep["ok"], "counts": c,
                 "scope": rep.get("scope", "全部照片")}))
            problems = sum(c.values())
            if problems == 0:
                self._finish(_tr("完整性校验完成：{p1} 张全部正常").format(p1=rep['total']))
            else:
                self._finish(
                    _tr("完整性校验：{p1} 张中 {p2} 张需注意").format(p1=rep['total'], p2=problems)
                    + _tr("（缺失 {p1} · 被改动 {p2}").format(p1=c['missing'], p2=c['changed'])
                    + _tr(" · 缩略图丢失 {p1} · 分析失败 {p2}）").format(p1=c['thumbMissing'], p2=c['error']))
            return rep

        self._spawn("integrity", "完整性校验", self._run_with_progress(task, "完整性校验"))
        return ""

    @Slot(result=str)
    @Slot(str, result=str)
    def deepDecodeCheck(self, folder: str = "") -> str:
        """后台**深度解码检查**（0.5.64）：对非常规格式逐张试全图解码，
        发现损坏文件写 photos.decode_error=1，完成后重跑完整性校验刷新报告。

        使用独立 sqlite 连接（后台线程写共享连接有语句缓存竞态）。
        """
        import sqlite3

        def task(prog):
            from photo_manager.core.integrity import check_integrity, deep_decode_check

            conn = sqlite3.connect(self.db.path, timeout=30)
            try:
                rep = deep_decode_check(conn, prog, folder=folder)
            finally:
                conn.close()
            # 深检完成后重跑只读校验刷新报告（含新标记的 decodeError 类别）
            rep2 = check_integrity(self.db, prog, folder=folder)
            self._integrity = rep2
            c = rep2["counts"]
            self.integrityFinished.emit(json.dumps(
                {"total": rep2["total"], "ok": rep2["ok"], "counts": c,
                 "scope": rep2.get("scope", "全部照片")}))
            if rep["damaged"]:
                self._finish(
                    _tr("深度解码检查：扫描 {p1} 张非常规格式，").format(p1=rep['scanned'])
                    + _tr("发现损坏 {p1} 张（用时 {p2} 秒）").format(p1=rep['damaged'], p2=rep['elapsed']))
            else:
                self._finish(
                    _tr("深度解码检查：扫描 {p1} 张非常规格式，").format(p1=rep['scanned'])
                    + _tr("未发现损坏（用时 {p1} 秒）").format(p1=rep['elapsed']))
            return rep

        self._spawn("deepdecode", "深度解码检查", self._run_with_progress(task, "深度解码检查"))
        return ""

    @Slot(str, int, int, result="QVariant")
    def integrityIssues(self, kind: str, offset: int = 0, limit: int = 200) -> list:
        """某类问题的照片清单（供 UI 展示）。"""
        rep = self._integrity
        if not rep or kind not in rep["ids"]:
            return []
        ids = rep["ids"][kind][offset:offset + limit]
        if not ids:
            return []
        q = ",".join("?" for _ in ids)
        rows = self.db.conn.execute(
            "SELECT id, file_name, folder_path, thumbnail_path, taken_at, status"
            f" FROM photos WHERE id IN ({q})", tuple(ids),
        ).fetchall()
        by_id = {r[0]: r for r in rows}
        out = []
        for pid in ids:
            r = by_id.get(pid)
            if not r:
                continue
            out.append({"id": r[0], "name": r[1], "folder": r[2],
                        "thumb": self._thumb_url(r[3]), "takenAt": r[4] or "",
                        "status": r[5] or ""})
        return out

    @Slot(str, result=int)
    def integrityRepair(self, kind: str) -> int:
        """修复某类问题：把照片置为 pending 重跑分析（重建缩略图/元数据/向量）。

        只重建库内派生数据，**绝不动原图**。missing 不可自动修复（返回 0）——
        文件是否真的丢了要由用户判断，程序不擅自清除记录（不删除红线）。
        """
        from photo_manager.core.integrity import REPAIRABLE
        if kind not in REPAIRABLE:
            return 0
        rep = self._integrity
        if not rep:
            return 0
        ids = rep["ids"].get(kind, [])
        if not ids:
            return 0
        conn = self.db.conn
        n = 0
        for pid in ids:
            cur = conn.execute(
                "UPDATE photos SET status='pending', error=NULL"
                " WHERE id=? AND status != 'missing'", (pid,))
            n += cur.rowcount
        conn.commit()
        if n:
            self._start_auto_chain()
        return n

    # ---------- 缺失照片两阶段清除：missing → 待删除（可恢复）→ 彻底删除 ----------

    @Slot(int, int, result="QVariant")
    def missingList(self, offset: int = 0, limit: int = 500) -> list:
        """第一阶段列表：被重建索引标记为 missing 的照片（文件已在系统外被删除）。"""
        rows = self.db.conn.execute(
            "SELECT id, file_name, folder_path, thumbnail_path, taken_at"
            " FROM photos WHERE status='missing' ORDER BY folder_path, file_name"
            " LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [
            {"id": r[0], "name": r[1], "folder": r[2],
             "thumb": self._thumb_url(r[3]), "takenAt": r[4] or ""}
            for r in rows
        ]

    @Slot(int, int, result="QVariant")
    def pendingDeleteList(self, offset: int = 0, limit: int = 500) -> list:
        """第二阶段列表：已移入待删除区、等待彻底删除的照片。"""
        rows = self.db.conn.execute(
            "SELECT id, file_name, folder_path, thumbnail_path, taken_at"
            " FROM photos WHERE status='pending_delete' ORDER BY folder_path, file_name"
            " LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [
            {"id": r[0], "name": r[1], "folder": r[2],
             "thumb": self._thumb_url(r[3]), "takenAt": r[4] or ""}
            for r in rows
        ]

    @Slot("QVariant", result=int)
    def moveToPendingDelete(self, ids) -> int:
        """第一阶段操作：missing → 待删除（可恢复）。仅对 missing 状态生效。"""
        n = 0
        for i in (ids or []):
            pid = int(i)
            cur = self.db.conn.execute(
                "UPDATE photos SET status='pending_delete' WHERE id=? AND status='missing'",
                (pid,),
            )
            if cur.rowcount:
                # photos_au 触发器随 UPDATE 重建了 FTS 行，需移除以保持不可搜索
                self.db.conn.execute("DELETE FROM photos_fts WHERE rowid=?", (pid,))
                self.db.conn.execute("DELETE FROM ocr_fts WHERE rowid=?", (pid,))
                n += 1
        self.db.conn.commit()
        return n

    @Slot("QVariant", result=int)
    def restorePendingDelete(self, ids) -> int:
        """从待删除区恢复：回 missing；文件若已回到原位则转 pending 重新走分析。"""
        n = 0
        for i in (ids or []):
            pid = int(i)
            row = self.db.conn.execute(
                "SELECT file_path, ocr_text FROM photos"
                " WHERE id=? AND status='pending_delete'",
                (pid,),
            ).fetchone()
            if not row:
                continue
            if os.path.exists(row[0]):
                # photos_au 触发器随 UPDATE 自动恢复 photos_fts
                self.db.conn.execute(
                    "UPDATE photos SET status='pending', error=NULL WHERE id=?", (pid,))
                if row[1]:
                    self.db.conn.execute(
                        "INSERT OR REPLACE INTO ocr_fts(rowid, ocr_text) VALUES (?,?)",
                        (pid, row[1]),
                    )
            else:
                self.db.conn.execute(
                    "UPDATE photos SET status='missing', error=NULL WHERE id=?", (pid,))
                self.db.conn.execute("DELETE FROM photos_fts WHERE rowid=?", (pid,))
                self.db.conn.execute("DELETE FROM ocr_fts WHERE rowid=?", (pid,))
            n += 1
        self.db.conn.commit()
        return n

    @Slot("QVariant", result=int)
    def purgeDeleted(self, ids) -> int:
        """第二阶段操作：彻底删除待删除区照片的记录与缩略图文件（不可恢复）。

        只对 status='pending_delete' 的记录生效；原照片文件早已在系统外被删除，
        此处清除的是库内残留记录与缩略图缓存，不触碰任何现存照片文件。
        """
        n = 0
        for i in (ids or []):
            pid = int(i)
            row = self.db.conn.execute(
                "SELECT thumbnail_path FROM photos"
                " WHERE id=? AND status='pending_delete'",
                (pid,),
            ).fetchone()
            if not row:
                continue
            if row[0]:
                try:
                    tp = Path(row[0])
                    if not tp.is_absolute():
                        tp = Path(self.db.path).parent / tp
                    if tp.exists():
                        tp.unlink()
                except Exception:
                    log.warning("缩略图删除失败: %s", row[0], exc_info=True)
            self.db.conn.execute("DELETE FROM photos WHERE id=?", (pid,))
            n += 1
        self.db.conn.commit()
        return n

    @Slot(result=str)
    def initDatabase(self) -> str:
        """初始化数据库：先按当前时间备份，再清空全部记录。

        流程：
          1) 备份到 <库目录>/backups/library_YYYYMMDD_HHMMSS.db（文件名即备份时间）
          2) 清空照片/人脸/OCR/事件/人物/标签/语义向量/扫描根目录等全部业务记录
          3) VACUUM 收缩文件

        **不触碰任何原始照片文件**；缩略图缓存也保留（重新入库会自动重建）。
        meta 表保留（存 schema 版本等）。
        返回 JSON 字符串：{"ok","backup","photos","error"}
        """
        import json as _json

        out = {"ok": False, "backup": "", "photos": 0, "error": ""}

        # 1) 先备份
        try:
            from photo_manager.core.backup import backup_db

            target = backup_db(self.db)
            out["backup"] = str(target)
        except Exception as e:
            out["error"] = _tr("备份失败：{p1}: {p2}").format(p1=type(e).__name__, p2=e)
            self._finish(out["error"])
            return _json.dumps(out, ensure_ascii=False)

        # 2) 清空业务表（先子表后主表；FTS 用 DELETE 即可）
        conn = self.db.conn
        try:
            try:
                out["photos"] = int(
                    conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0])
            except Exception as e:  # noqa: BLE001  # 仅用于展示，失败不影响清空
                log.warning("初始化：统计照片数失败：%s", e)
            # 业务表：先子表后主表（photos 的删除触发器会自动清掉 FTS 对应条目）
            for t in ("photo_embeddings", "photo_tags", "faces", "ocr_texts",
                      "event_photos", "events", "persons",
                      "album_photos", "albums", "library_imports",
                      "move_out_records", "analysis_state", "scan_roots", "photos"):
                try:
                    conn.execute(f"DELETE FROM {t}")
                except Exception as e:  # 旧库可能没有某些表，跳过即可
                    log.warning("初始化：清空 %s 失败：%s", t, e)
            conn.commit()
            # FTS5 两种表要区别对待：
            # - photos_fts 是 external content 表(content='photos')，必须用 'delete-all'，
            #   直接 DELETE FROM 会破坏索引并导致后续报 "database disk image is malformed"
            # - ocr_fts 是普通表(trigram)，'delete-all' 不适用，只能用 DELETE
            try:
                conn.execute("INSERT INTO photos_fts(photos_fts) VALUES('delete-all')")
            except Exception as e:
                log.warning("初始化：清空 photos_fts 失败：%s", e)
            try:
                conn.execute("DELETE FROM ocr_fts")
            except Exception as e:
                log.warning("初始化：清空 ocr_fts 失败：%s", e)
            conn.commit()
            try:
                conn.execute("VACUUM")
            except Exception as e:
                log.warning("初始化：VACUUM 失败：%s", e)
            out["ok"] = True
        except Exception as e:
            out["error"] = _tr("清空失败：{p1}: {p2}").format(p1=type(e).__name__, p2=e)

        if out["ok"]:
            self.photosChanged.emit()
            self._finish(
                _tr("数据库已初始化（清空 {p1} 条照片记录），备份：").format(p1=out['photos'])
                + f"{Path(out['backup']).name}")
        else:
            self._finish(out["error"])
        return _json.dumps(out, ensure_ascii=False)

    # ---------- 扫描入库 ----------
    # ⚠️ PySide6 教训：QML→Python 槽调用的参数个数必须与 @Slot 声明**完全一致**，
    # 不匹配时会被**静默丢弃**（无异常、无日志，Python 侧根本不执行）。
    # 因此 QML 只暴露 1 参槽（ingest/ingestFlat/ingestMany/ingestManyFlat）；
    # 带 recursive 参数的多参形式仅供 Python 侧（定时任务等）直接方法调用。

    def _start_ingest(self, folders: list[str], recursive: bool) -> bool:
        if getattr(self, "_ingest_suspended", False):
            return False  # gui_check A16k 挂起导入，仅验证信号链路
        folders = [str(f) for f in (folders or []) if f]
        if not folders:
            return False
        with self._busy_lock:
            if self._busy > 0:
                # 0.6.10：导入排队——有任务在跑时新导入不再被拒绝丢弃
                # （旧文案"扫描已取消"还会误导用户以为自己的操作出了问题），
                # 而是进入 FIFO 队列，当前任务结束后 _release_busy 自动接续。
                # 相同文件夹集合的重复排队合并为一条。
                queue = getattr(self, "_pending_ingests", None)
                if queue is None:
                    queue = self._pending_ingests = []
                entry = (tuple(sorted(set(folders))), bool(recursive))
                for i, (qf, qr) in enumerate(queue):
                    if qf == entry[0]:
                        queue[i] = (qf, qr or recursive)
                        break
                else:
                    if len(queue) >= 5:
                        self._finish(_tr("导入已取消：排队上限 5 个，"
                                         "请等当前任务完成后再试"))
                        return False
                    queue.append(entry)
                n = len(queue)
                self._finish(_tr("导入已排队（第 {p1} 个）：当前任务结束后自动开始")
                             .format(p1=n))
                return True
            self._busy = 1
        if len(folders) == 1:
            self.message.emit(_tr("正在扫描照片，请稍候…"))
        else:
            self.message.emit(_tr("正在扫描 {p1} 个文件夹，请稍候…").format(p1=len(folders)))
        threading.Thread(target=self._ingest_many_worker,
                         args=(folders, recursive), daemon=True).start()
        return True

    def _drain_ingest_queue(self) -> None:
        """0.6.10：busy 释放后接续排队的导入（FIFO，复用 _clip_pending 模式）。"""
        queue = getattr(self, "_pending_ingests", None)
        if not queue:
            return
        folders, recursive = queue.pop(0)
        self._start_ingest(list(folders), recursive)

    @Slot(str)
    def ingest(self, folder: str) -> None:
        """扫描入库（含子文件夹）。QML 入口，1 参。"""
        self._start_ingest([folder], True)

    @Slot(bool)
    def setIngestSuspended(self, on: bool) -> None:
        """挂起/恢复导入（gui_check A16k 验证信号链路时防止真实整盘扫描）。"""
        self._ingest_suspended = bool(on)

    @staticmethod
    def _qml_path_list(v) -> list[str]:
        """QML 信号 var 参数 → [str]。

        QML `signal xxx(var paths)` 发射 JS 数组时，PySide6 交付的是 QJSValue
        （**不可迭代**）：直接 `[str(p) for p in paths]` 抛 TypeError，且槽内
        异常被 Qt 静默吞掉 —— 多选导入曾因此无任何反馈地失败（v0.5.21 修复）。
        """
        to_variant = getattr(v, "toVariant", None)
        if callable(to_variant):
            v = to_variant()
        if isinstance(v, (list, tuple)):
            return [str(p) for p in v if p]
        if isinstance(v, str):
            return [v] if v else []
        return []

    @Slot("QVariant")
    def attachQmlSignals(self, root) -> None:
        """把 QML 选择器/目录树的导入信号直接连到 Python 槽。

        ⚠️ 不走 QML→Python 的方法调用：QML 侧 `LibraryBridge.ingest(x)` 这类
        调用在特定环境下会被 PySide 静默丢弃（无异常、不执行，原因未明），
        而信号→槽的 Qt 原生连接始终可靠。main.py / gui_check 在引擎加载后
        调用本方法完成接线；QML 的 onPathChosen 等 handler 只负责状态栏文案。
        """
        from PySide6.QtCore import QObject

        # ⚠️ 这里必须用普通 Python 闭包连接（而非直接连 @Slot 方法）：
        # pathChosen → self.ingest（Qt 原生信号→槽）在实测中不投递，
        # 而闭包连接与消息间谍同机制，始终可靠。
        for obj_name in ("scanPicker",):
            pk = root.findChild(QObject, obj_name)
            if pk is not None:
                pk.pathChosen.connect(
                    lambda folder: self._start_ingest([str(folder)], True))
                pk.pathsChosen.connect(
                    lambda paths: self._start_ingest(
                        self._qml_path_list(paths), True))
        ft = root.findChild(QObject, "folderTree")
        if ft is not None:
            ft.ingestRequested.connect(
                lambda folder: self._start_ingest([str(folder)], True))
            ft.ingestMany.connect(
                lambda paths: self._start_ingest(
                    self._qml_path_list(paths), True))
        # 备份 / 恢复 / 元数据导出导入（同样走闭包直连，规避 QML→Python 丢调用）
        wiring = (
            ("backupPicker", "pathChosen", lambda folder: self.backupTo(str(folder))),
            ("restorePicker", "fileChosen", lambda path: self.restoreBackup(str(path))),
            ("syncOutPicker", "fileChosen", lambda path: self.syncExport(str(path))),
            ("syncInPicker", "fileChosen", lambda path: self.syncImport(str(path))),
        )
        for obj_name, sig_name, cb in wiring:
            pk = root.findChild(QObject, obj_name)
            if pk is not None:
                sig = getattr(pk, sig_name, None)
                if sig is not None:
                    sig.connect(cb)

    @Slot(str)
    def ingestFlat(self, folder: str) -> None:
        """只扫描 folder 顶层（不含子文件夹）。QML 入口，1 参。"""
        self._start_ingest([folder], False)

    @Slot("QVariantList")
    def ingestMany(self, folders) -> None:
        """批量扫描入库（含子文件夹）。QML 入口，1 参。"""
        self._start_ingest([str(f) for f in (folders or []) if f], True)

    @Slot("QVariantList")
    def ingestManyFlat(self, folders) -> None:
        """批量扫描入库（只扫顶层）。QML 入口，1 参。"""
        self._start_ingest([str(f) for f in (folders or []) if f], False)

    def _ingest_many_worker(self, folders: list[str], recursive: bool = True) -> None:
        from photo_manager.core.pipeline import IngestPipeline

        total_new = total_fail = 0
        try:
            for i, folder in enumerate(folders):

                def prog(done, total, path=""):
                    self.taskProgress.emit(done or 0, total or 0, _tr("扫描照片 {p1}/{p2}").format(p1=i + 1, p2=len(folders)))

                pipe = IngestPipeline(self.db, Path(self.db.path).parent)
                stats = pipe.ingest(folder, progress_cb=prog, recursive=recursive,
                                    copy_root=self._copy_roots_for(folder))
                total_new += stats.get("indexed", 0)
                total_fail += stats.get("failed", 0)
            self._finish(
                _tr("扫描完成：新增 {p1} 张").format(p1=total_new)
                + (_tr("，失败 {p1} 张").format(p1=total_fail) if total_fail else "")
            )
            self.photosChanged.emit()
        except Exception as e:
            log.exception("GUI 批量扫描失败")
            self._finish(_tr("扫描失败：{p1}").format(p1=e))
        finally:
            self._release_busy()
        self._start_auto_chain()
        self._maybe_auto_clip()

    # ---------- 照片库根目录 / 复制入库（C12） ----------
    @staticmethod
    def _cfg():
        from PySide6.QtCore import QSettings

        return QSettings("PhotoManager", "PhotoManager")

    def _library_roots_list(self) -> list[str]:
        """照片库根目录列表（每行一个，绝对化）。"""
        text = str(self._cfg().value("libraryRoots", "") or "")
        out = []
        for line in text.replace("\r", "\n").split("\n"):
            p = line.strip()
            if p and os.path.isabs(p.replace("/", os.sep) if os.name == "nt" else p):
                out.append(os.path.abspath(p).replace("\\", "/"))
        return out

    @Slot(result=str)
    def libraryRoots(self) -> str:
        return str(self._cfg().value("libraryRoots", "") or "")

    @Slot(str)
    def setLibraryRoots(self, text: str) -> None:
        self._cfg().setValue("libraryRoots", text or "")

    @Slot(str, result=bool)
    def addLibraryRoot(self, path: str) -> bool:
        """追加一个照片库根目录（绝对化+去重；目录不存在返回 False）。"""
        p = os.path.abspath(str(path).strip()).replace("\\", "/")
        if not p or not os.path.isdir(p):
            return False
        roots = self._library_roots_list()
        if p in roots:
            return True
        roots.append(p)
        self._cfg().setValue("libraryRoots", "\n".join(roots))
        return True

    @Slot(str, str, result=str)
    def pickFolder(self, title: str, start_dir: str = "") -> str:
        """系统原生文件夹选择窗口（0.5.56：自带"新建文件夹"按钮）。
        用户取消返回空串；选中返回绝对路径。"""
        try:
            from PySide6.QtWidgets import QFileDialog

            p = QFileDialog.getExistingDirectory(
                None, title or "选择文件夹", start_dir or "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
            return p or ""
        except Exception:
            log.exception("系统文件夹选择窗口失败")
            return ""

    @Slot(result=bool)
    def copyToLibraryEnabled(self) -> bool:
        v = self._cfg().value("copyToLibrary", False)
        return str(v).lower() in ("true", "1")

    @Slot(bool)
    def setCopyToLibraryEnabled(self, on: bool) -> None:
        self._cfg().setValue("copyToLibrary", bool(on))

    def _copy_roots_for(self, anchor: str) -> list[str]:
        """导入 anchor 文件夹时是否需要复制入库：开启开关且 anchor 不在任一
        照片库根目录下 → 返回全部库根（pipeline 逐张挑选空间足够的根）；
        否则空列表（就地登记）。"""
        if not self.copyToLibraryEnabled():
            return []
        roots = self._library_roots_list()
        if not roots:
            return []
        from photo_manager.core.library import under_any

        if under_any(anchor, roots):
            return []
        return roots

    @Slot(result="QVariant")
    def libraryRootsInfo(self) -> list[dict]:
        """照片库根目录信息（供设置页列表展示：路径/剩余空间/是否默认根）。"""
        import shutil

        out = []
        for i, r in enumerate(self._library_roots_list()):
            info = {"path": r, "primary": i == 0, "exists": os.path.isdir(r),
                    "freeGB": 0.0, "totalGB": 0.0}
            try:
                du = shutil.disk_usage(r)
                info["freeGB"] = round(du.free / 1024 ** 3, 1)
                info["totalGB"] = round(du.total / 1024 ** 3, 1)
            except OSError:
                pass
            out.append(info)
        return out

    # ---------- 定时任务执行方式（0.5.51 路线 B：OS 级调度） ----------
    _OS_TASK_NAME = "PhotoManager 定时任务"

    # 0.5.64：schtasks 子进程必须 CREATE_NO_WINDOW——GUI 程序启动控制台
    # 进程若无此标志，Windows 会闪出一个控制台窗口（用户报「移入定时任务
    # 菜单时弹窗闪一下消失」：onAboutToShow→scheduleOsRegistered→schtasks）。
    _PROC_NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0

    @Slot(result=str)
    def scheduleEngine(self) -> str:
        """定时执行方式：internal=程序内计时（默认，需程序在跑） /
        os=系统任务计划（Windows 任务计划 / 麒麟 systemd --user，关机不错过）。"""
        return str(self._cfg().value("schedule/engine", "internal") or "internal")

    @Slot(str, result=str)
    def setScheduleEngine(self, mode: str) -> str:
        """切换定时执行方式并注册/注销对应系统任务。返回状态文本。"""
        mode = (mode or "internal").lower()
        if mode not in ("internal", "os"):
            return "未知执行方式"
        cfg = self._cfg()
        if mode == "os":
            # 注册前先校验：必须有执行项与时间，否则系统任务空跑
            if not (self.scheduleCheckEnabled() or self.scheduleAnalyzeEnabled()):
                return "请先勾选定时执行项（检查文件夹/智能分析）"
            if self.scheduleMode() == "off":
                return "请先选择执行方式（仅一次/每日）"
            ok, detail = self._register_os_task()
            if not ok:
                return _tr("注册系统任务失败：{p1}").format(p1=detail)
            cfg.setValue("schedule/engine", "os")
            self._os_registered_cache = True
            return _tr("已注册{p1}（关机不错过，到点自动唤起程序执行）").format(p1=detail)
        # 切回程序内计时：注销系统任务（忽略不存在）
        self._unregister_os_task()
        cfg.setValue("schedule/engine", "internal")
        self._os_registered_cache = False
        return "已切回程序内计时（需程序保持运行，配合开机启动+托盘）"

    @Slot(result=bool)
    def scheduleOsRegistered(self) -> bool:
        """系统任务计划当前是否已注册。

        0.5.64 两修：① subprocess 加 CREATE_NO_WINDOW（控制台闪窗）；
        ② 结果缓存——此前每次菜单 onAboutToShow 都同步跑一次 schtasks
        （UI 线程阻塞数百 ms），注册状态只在切换执行方式时变化，缓存即可。
        """
        if self._os_registered_cache is not None:
            return self._os_registered_cache
        val = self._query_os_registered()
        self._os_registered_cache = val
        return val

    def _query_os_registered(self) -> bool:
        """实际查询 OS 定时任务注册状态（无缓存）。"""
        if sys.platform.startswith("win"):
            import subprocess  # noqa: PLC0415

            try:
                r = subprocess.run(
                    ["schtasks", "/Query", "/TN", self._OS_TASK_NAME],
                    capture_output=True, timeout=15,
                    creationflags=self._PROC_NO_WINDOW)
                return r.returncode == 0
            except Exception:
                return False
        # Linux：systemd --user timer 文件存在即视为已注册
        return self._systemd_timer_path().exists()

    def _systemd_unit_dir(self) -> Path:
        return Path.home() / ".config" / "systemd" / "user"

    def _systemd_timer_path(self) -> Path:
        return self._systemd_unit_dir() / "photomanager-schedule.timer"

    def _os_task_exe(self) -> str | None:
        """注册用的可执行文件（仅打包版；开发模式注册了也没意义）。"""
        import sys as _sys  # noqa: PLC0415

        if not getattr(_sys, "frozen", False):
            return None
        from PySide6.QtCore import QCoreApplication

        return QCoreApplication.applicationFilePath()

    def _register_os_task(self) -> tuple[bool, str]:
        """注册 OS 级定时任务。返回 (成功, 描述)。"""
        exe = self._os_task_exe()
        if exe is None:
            return False, "仅打包版支持（开发模式请用程序内计时）"
        mode = self.scheduleMode()
        if sys.platform.startswith("win"):
            return self._register_windows_task(exe, mode)
        return self._register_systemd_timer(exe, mode)

    def _register_windows_task(self, exe: str, mode: str) -> tuple[bool, str]:
        """Windows：schtasks + XML（StartWhenAvailable=关机错过也补跑）。"""
        import subprocess  # noqa: PLC0415
        import tempfile  # noqa: PLC0415

        if mode == "once":
            at = self.scheduleOnceAt().replace(" ", "T") or "2026-01-01T09:00:00"
            if len(at) == 16:
                at += ":00"
            trigger = ('<TimeTrigger><StartBoundary>%s</StartBoundary>'
                       '<Enabled>true</Enabled></TimeTrigger>' % at)
            desc = "Windows 任务计划（一次性 %s）" % at[:16].replace("T", " ")
        else:
            hm = (self.scheduleTime() or "09:00") + ":00"
            trigger = ('<CalendarTrigger><StartBoundary>2026-01-01T%s</StartBoundary>'
                       '<Enabled>true</Enabled>'
                       '<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>'
                       '</CalendarTrigger>' % hm)
            desc = "Windows 任务计划（每日 %s）" % hm[:5]
        xml = self._windows_task_xml(exe, trigger)
        try:
            with tempfile.NamedTemporaryFile(
                    "w", suffix=".xml", encoding="utf-16", delete=False) as f:
                f.write(xml)
                xml_path = f.name
            r = subprocess.run(
                ["schtasks", "/Create", "/TN", self._OS_TASK_NAME,
                 "/XML", xml_path, "/F"],
                capture_output=True, timeout=30,
                creationflags=self._PROC_NO_WINDOW)
            try:
                os.unlink(xml_path)
            except OSError:
                pass
            if r.returncode != 0:
                return False, (r.stderr or r.stdout or b"").decode(
                    "utf-8", "replace").strip()[:120]
            return True, desc
        except Exception as e:  # noqa: BLE001
            return False, str(e)[:120]

    @staticmethod
    def _windows_task_xml(exe: str, trigger_xml: str) -> str:
        """Windows 任务计划 XML（StartWhenAvailable=关机错过开机后补跑）。"""
        return (
            '<?xml version="1.0" encoding="UTF-16"?>'
            '<Task xmlns="http://schemas.microsoft.com/windows/2004/2/mntc">'
            '<RegistrationInfo><Description>PhotoManager 定时任务'
            '（检查照片文件夹/智能分析）</Description></RegistrationInfo>'
            '<Triggers>%s</Triggers>'
            '<Settings><StartWhenAvailable>true</StartWhenAvailable>'
            '<ExecutionTimeLimit>PT4H</ExecutionTimeLimit>'
            '<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>'
            '</Settings>'
            '<Actions><Exec><Command>&quot;%s&quot;</Command>'
            '<Arguments>--scheduled-run</Arguments></Exec></Actions>'
            '<Principals><Principal><LogonType>InteractiveToken</LogonType>'
            '</Principal></Principals></Task>' % (trigger_xml, exe))

    def _register_systemd_timer(self, exe: str, mode: str) -> tuple[bool, str]:
        """麒麟/Linux：systemd --user service+timer（Persistent=错过补跑）。"""
        import subprocess  # noqa: PLC0415

        if mode == "once":
            at = self.scheduleOnceAt().replace("T", " ")
            oncal = at if len(at) == 16 else "2026-01-01 09:00"
            desc = "systemd 用户定时器（一次性 %s）" % oncal
        else:
            oncal = "*-*-* %s:00" % (self.scheduleTime() or "09:00")
            desc = "systemd 用户定时器（每日 %s）" % (self.scheduleTime() or "09:00")
        try:
            d = self._systemd_unit_dir()
            d.mkdir(parents=True, exist_ok=True)
            (d / "photomanager-schedule.service").write_text(
                "[Unit]\nDescription=PhotoManager scheduled run\n\n"
                "[Service]\nType=oneshot\nExecStart=\"%s\" --scheduled-run\n"
                % exe, encoding="utf-8")
            self._systemd_timer_path().write_text(
                "[Unit]\nDescription=PhotoManager schedule timer\n\n"
                "[Timer]\nOnCalendar=%s\nPersistent=true\n\n"
                "[Install]\nWantedBy=timers.target\n" % oncal, encoding="utf-8")
            r = subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True, timeout=30)
            if r.returncode != 0:
                return False, "systemctl --user 不可用（需 systemd 用户实例）"
            subprocess.run(
                ["systemctl", "--user", "enable", "--now",
                 "photomanager-schedule.timer"],
                capture_output=True, timeout=30)
            return True, desc
        except Exception as e:  # noqa: BLE001
            return False, str(e)[:120]

    def _unregister_os_task(self) -> None:
        """注销 OS 级定时任务（内部用；失败静默）。"""
        try:
            if sys.platform.startswith("win"):
                import subprocess  # noqa: PLC0415

                subprocess.run(
                    ["schtasks", "/Delete", "/TN", self._OS_TASK_NAME, "/F"],
                    capture_output=True, timeout=30,
                    creationflags=self._PROC_NO_WINDOW)
            else:
                import subprocess  # noqa: PLC0415

                subprocess.run(
                    ["systemctl", "--user", "disable", "--now",
                     "photomanager-schedule.timer"],
                    capture_output=True, timeout=30)
                for name in ("photomanager-schedule.service",
                             "photomanager-schedule.timer"):
                    try:
                        (self._systemd_unit_dir() / name).unlink(missing_ok=True)
                    except OSError:
                        pass
                subprocess.run(
                    ["systemctl", "--user", "daemon-reload"],
                    capture_output=True, timeout=30)
        except Exception:
            log.debug("注销系统定时任务失败", exc_info=True)

    # ---------- 检查照片文件夹（C12：自动收录新增 + 报告缺失） ----------
    @Slot(bool)
    def folderCheck(self, analyze_after: bool = False) -> None:
        """检查照片文件夹（后台）：对每个扫描根与照片库根重新扫描——
        自动收录新增照片；再跑完整性比对，发现被人工删除/改动的照片。
        analyze_after=True 时，检查完成后接着运行智能分析链（定时任务用）。"""
        with self._busy_lock:
            if self._busy > 0:
                self._finish("检查已取消：有任务正在运行，请稍候")
                return
            self._busy = 1
        self.message.emit(_tr("正在检查照片文件夹…"))
        threading.Thread(target=self._folder_check_worker,
                         args=(bool(analyze_after),), daemon=True).start()

    def _folder_check_worker(self, analyze_after: bool) -> None:
        from photo_manager.core.integrity import check_integrity
        from photo_manager.core.pipeline import IngestPipeline

        roots = [r for r in self._library_roots_list() if os.path.isdir(r)]
        for (p,) in self.db.conn.execute(
            "SELECT path FROM scan_roots"
        ).fetchall():
            if p and p not in roots and os.path.isdir(p):
                roots.append(p)
        added = failed = 0
        try:
            def prog(done, total, path=""):
                self.taskProgress.emit(done or 0, total or 0, "检查照片文件夹")

            for r in roots:
                pipe = IngestPipeline(self.db, Path(self.db.path).parent)
                stats = pipe.ingest(r, progress_cb=prog, recursive=True,
                                    copy_root=self._copy_roots_for(r),
                                    register_roots=False)
                added += stats.get("indexed", 0)
                failed += stats.get("failed", 0)
            rep = check_integrity(self.db)
            self._integrity = rep
            self.photosChanged.emit()
            cnt = rep.get("counts", {})
            self._finish(
                _tr("检查完成：新增收录 {p1} 张；缺失 {p2} 张、").format(p1=added, p2=cnt.get('missing', 0))
                + _tr("被改动 {p1} 张（详情见完整性校验）").format(p1=cnt.get('changed', 0))
            )
        except Exception as e:
            log.exception("检查照片文件夹失败")
            self._finish(_tr("检查失败：{p1}").format(p1=e))
        finally:
            self._release_busy()
        if analyze_after:
            self._start_auto_chain()
        self._maybe_auto_clip()

    # ---------- 定时任务（C12：一次 / 每日，运行期间生效） ----------
    def start_scheduler(self) -> None:
        """启动定时器（主线程事件循环驱动，每 30s 检查一次到期）。"""
        from PySide6.QtCore import QTimer

        self._sched_timer = QTimer(self)
        self._sched_timer.setInterval(30_000)
        self._sched_timer.timeout.connect(self._sched_tick)
        self._sched_timer.start()
        # 0.5.49：启动 10s 后按需补跑自动语义索引——开关已开但有存量照片
        # 从未生成向量时（老用户典型场景），不开工就永远不出向量。
        # 无待处理照片时不动作（不会白加载 760MB 模型）。
        QTimer.singleShot(10_000, self._maybe_auto_clip)

    @Slot()
    def _sched_tick(self) -> None:
        cfg = self._cfg()
        mode = str(cfg.value("schedule/mode", "off") or "off").lower()
        if mode not in ("once", "daily"):
            return
        do_check = str(cfg.value("schedule/folderCheck", "false")).lower() in ("true", "1")
        do_analyze = str(cfg.value("schedule/analyze", "false")).lower() in ("true", "1")
        if not (do_check or do_analyze):
            return
        from datetime import datetime as _dt

        from photo_manager.core.library import schedule_due as schedule_due_on

        due = schedule_due_on(
            mode,
            str(cfg.value("schedule/time", "09:00") or ""),
            str(cfg.value("schedule/lastRun", "") or ""),
            str(cfg.value("schedule/onceAt", "") or ""),
            _dt.now(),
        )
        if not due:
            return
        if self._busy > 0:
            return  # 有任务在跑，下轮再试（每日 lastRun 未写，不会漏跑）
        today = _dt.now().strftime("%Y-%m-%d")
        if mode == "daily":
            cfg.setValue("schedule/lastRun", today)
        else:
            cfg.setValue("schedule/mode", "off")  # 一次性：执行后自动关闭
        names = [n for n, on in ((_tr("检查照片文件夹"), do_check),
                                 (_tr("智能分析"), do_analyze)) if on]
        self.message.emit(_tr("定时任务触发：") + " + ".join(names))
        if do_check:
            self.folderCheck(do_analyze)
        else:
            self.autoAnalyze()

    # ---------- 定时任务设置读写 ----------
    @Slot(result=str)
    def scheduleMode(self) -> str:
        return str(self._cfg().value("schedule/mode", "off") or "off")

    @Slot(str)
    def setScheduleMode(self, mode: str) -> None:
        self._cfg().setValue("schedule/mode", (mode or "off").lower())

    @Slot(result=str)
    def scheduleTime(self) -> str:
        return str(self._cfg().value("schedule/time", "09:00") or "09:00")

    @Slot(str)
    def setScheduleTime(self, text: str) -> None:
        self._cfg().setValue("schedule/time", (text or "09:00").strip())

    @Slot(result=str)
    def scheduleOnceAt(self) -> str:
        return str(self._cfg().value("schedule/onceAt", "") or "")

    @Slot(str)
    def setScheduleOnceAt(self, text: str) -> None:
        self._cfg().setValue("schedule/onceAt", (text or "").strip())

    @Slot(result=bool)
    def scheduleCheckEnabled(self) -> bool:
        return str(self._cfg().value("schedule/folderCheck", "false")).lower() in ("true", "1")

    @Slot(bool)
    def setScheduleCheckEnabled(self, on: bool) -> None:
        self._cfg().setValue("schedule/folderCheck", bool(on))

    @Slot(result=bool)
    def scheduleAnalyzeEnabled(self) -> bool:
        return str(self._cfg().value("schedule/analyze", "false")).lower() in ("true", "1")

    @Slot(bool)
    def setScheduleAnalyzeEnabled(self, on: bool) -> None:
        self._cfg().setValue("schedule/analyze", bool(on))

    # ---------- 阶段 3：重复 / 备份 / 同步 / 标签 ----------
    @Slot(int, result="QVariant")
    def duplicates(self, dist: int = 6) -> list[dict]:
        from photo_manager.core.duplicates import DuplicateScanner

        return DuplicateScanner(self.db).find_duplicates(dist=dist)

    @Slot(int, result=str)
    def duplicatesJson(self, dist: int = 6) -> str:
        """重复组列表（JSON 字符串）。

        0.5.35：QVariant 槽返回的嵌套 dict→list→dict 结构在跨 QML 边界时
        内层 list 会丢失（model.members 为 undefined，PySide 转换问题），
        改用 JSON 字符串桥接（同 sceneSuggestionsFinished 模式）。
        """
        import json

        from photo_manager.core.duplicates import DuplicateScanner

        return json.dumps(
            DuplicateScanner(self.db).find_duplicates(dist=dist),
            ensure_ascii=False,
        )

    @Slot(result=str)
    def backupNow(self) -> str:
        from photo_manager.core.backup import backup_db

        with self._busy_lock:
            if self._busy > 0:
                self._finish("备份已取消：有任务正在运行，请稍候")
                return ""
            self._busy = 1
        self.message.emit(_tr("正在备份数据库…"))
        def worker():
            try:
                target = backup_db(self.db)
                self._finish(_tr("数据库已备份 → {p1}").format(p1=target))
            except Exception as e:
                log.exception("备份失败")
                self._finish(_tr("备份失败：{p1}").format(p1=e))
            finally:
                self._release_busy()

        threading.Thread(target=worker, daemon=True).start()
        return ""

    @Slot(str, result=str)
    def backupTo(self, out_dir: str) -> str:
        """备份到用户指定目录（生成 library_<时间戳>.db）。"""
        from photo_manager.core.backup import backup_db

        with self._busy_lock:
            if self._busy > 0:
                self._finish("备份已取消：有任务正在运行，请稍候")
                return ""
            self._busy = 1
        self.message.emit(_tr("正在备份到指定目录…"))
        def worker():
            try:
                target = backup_db(self.db, out_dir)
                self._finish(_tr("数据库已备份 → {p1}").format(p1=target))
            except Exception as e:
                log.exception("备份失败")
                self._finish(_tr("备份失败：{p1}").format(p1=e))
            finally:
                self._release_busy()

        threading.Thread(target=worker, daemon=True).start()
        return ""

    @Slot(result=str)
    def backupOnExit(self) -> str:
        """退出时自动备份（同步执行，保留最近 10 份）。"""
        from photo_manager.core.backup import backup_db

        try:
            target = backup_db(self.db, None, keep=10)
            return str(target)
        except Exception as e:
            log.exception("退出备份失败")
            return _tr("备份失败：{p1}").format(p1=e)

    @Slot(str, result=str)
    def exportCsv(self, out_path: str) -> str:
        """导出照片元数据 CSV（同步，供测试与归档）。"""
        from photo_manager.core.csv_export import export_metadata_csv

        try:
            target = export_metadata_csv(self.db, out_path)
            return str(target)
        except Exception as e:
            log.exception("CSV 导出失败")
            return _tr("CSV 导出失败：{p1}").format(p1=e)

    @Slot(str, result=str)
    def syncExport(self, out_path: str) -> str:
        from photo_manager.core.sync import MetadataSync

        with self._busy_lock:
            if self._busy > 0:
                self._finish("导出已取消：有任务正在运行，请稍候")
                return ""
            self._busy = 1
        self.message.emit(_tr("正在导出元数据…"))
        def worker():
            try:
                stats = MetadataSync(self.db).export(out_path)
                self._finish(_tr("元数据已导出：人物 {p1} · 人脸归属").format(p1=stats['persons'])
                             + _tr(" {p1} · 事件 {p2} · 标签").format(p1=stats['face_assign'], p2=stats['events'])
                             + f" {stats['photo_tags']}")
            except Exception as e:
                log.exception("元数据导出失败")
                self._finish(_tr("元数据导出失败：{p1}").format(p1=e))
            finally:
                self._release_busy()

        threading.Thread(target=worker, daemon=True).start()
        return str(out_path)

    @Slot(str, result=str)
    def syncImport(self, src_path: str) -> str:
        from photo_manager.core.sync import MetadataSync

        with self._busy_lock:
            if self._busy > 0:
                self._finish("导入已取消：有任务正在运行，请稍候")
                return ""
            self._busy = 1
        self.message.emit(_tr("正在导入元数据…"))
        def worker():
            try:
                stats = MetadataSync(self.db).import_from(src_path)
                self._finish(_tr("元数据已导入：人物 {p1} · 人脸归属").format(p1=stats['persons'])
                             + _tr(" {p1} · 事件 {p2} · 标签").format(p1=stats['matched_faces'], p2=stats['events'])
                             + _tr(" {p1}（未匹配照片").format(p1=stats['photo_tags'])
                             + f" {stats['unmatched_photos']}）")
            except Exception as e:
                log.exception("元数据导入失败")
                self._finish(_tr("元数据导入失败：{p1}").format(p1=e))
            finally:
                self._release_busy()

        threading.Thread(target=worker, daemon=True).start()
        return src_path

    @Slot(int, str, result=bool)
    def addTag(self, photo_id: int, tag: str) -> bool:
        tag = tag.strip()
        if not tag:
            return False
        self.db.conn.execute(
            "INSERT INTO photo_tags(photo_id, tag) VALUES (?,?) "
            "ON CONFLICT(photo_id, tag) DO NOTHING",
            (photo_id, tag),
        )
        self.db.conn.commit()
        # 不发 photosChanged：否则主界面 onPhotosChanged 会 showAll()+清空选择，
        # 导致给照片打标签时视图被重置。标签只是元数据，当前照片的展示由 InfoPanel 自行刷新。
        return True

    @Slot(int, str, result="bool")
    def removeTag(self, photo_id: int, tag: str) -> bool:
        cur = self.db.conn.execute(
            "DELETE FROM photo_tags WHERE photo_id=? AND tag=?", (photo_id, tag)
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    @Slot(int, result="QVariant")
    def photoTags(self, photo_id: int) -> list[str]:
        rows = self.db.conn.execute(
            "SELECT tag FROM photo_tags WHERE photo_id=? ORDER BY tag", (photo_id,)
        ).fetchall()
        return [r[0] for r in rows]

    # ---------- 评级 / 精选旗标 ----------
    @Slot(int, int, result=bool)
    def setRating(self, photo_id: int, rating: int) -> bool:
        """设置照片评级（0-5；0=清除）。不影响排序，仅元数据。"""
        rating = max(0, min(5, int(rating)))
        self.db.conn.execute(
            "UPDATE photos SET rating=? WHERE id=?", (rating, photo_id))
        self.db.conn.commit()
        return True

    @Slot(int, str, result=bool)
    def setFlag(self, photo_id: int, flag: str) -> bool:
        """设置旗标：'pick' 精选 / 'reject' 排除 / '' 清除。"""
        flag = (flag or "").strip()
        if flag not in ("", "pick", "reject"):
            return False
        self.db.conn.execute(
            "UPDATE photos SET flag=? WHERE id=?", (flag, photo_id))
        self.db.conn.commit()
        return True

    @Slot("QVariant", str, result=int)
    def setColorLabel(self, ids, color: str) -> int:
        """批量设置色标：red/yellow/green/blue/purple（支持中文单字 红/黄/绿/蓝/紫），
        空串清除。仅元数据，不动原图。返回受影响行数。"""
        from PySide6.QtQml import QJSValue

        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        from photo_manager.core.search import COLOR_LABELS, _COLOR_ALIAS

        color = (color or "").strip().lower()
        color = _COLOR_ALIAS.get((color or "").strip(), color)
        if color and color not in COLOR_LABELS:
            return 0
        ids = [int(i) for i in (ids or []) if i is not None]
        if not ids:
            return 0
        q = ",".join("?" for _ in ids)
        cur = self.db.conn.execute(
            f"UPDATE photos SET color_label = ? WHERE id IN ({q})",
            (color or None, *ids))
        self.db.conn.commit()
        return cur.rowcount

    @Slot(int, bool, result=bool)
    def setArchived(self, photo_id: int, archived: bool) -> bool:
        """归档单张：archived=True 从主时间轴隐藏（不删除、不动原图）。"""
        cur = self.db.conn.execute(
            "UPDATE photos SET archived = ? WHERE id = ?",
            (1 if archived else 0, photo_id))
        self.db.conn.commit()
        return cur.rowcount > 0

    @Slot("QVariant", bool, result=int)
    def setArchivedBatch(self, ids, archived: bool) -> int:
        """批量归档/取消归档；返回受影响行数。与"程序内不删除"红线一致。"""
        from PySide6.QtQml import QJSValue

        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        ids = [int(i) for i in ids if i is not None]
        if not ids:
            return 0
        q = ",".join("?" for _ in ids)
        cur = self.db.conn.execute(
            f"UPDATE photos SET archived = ? WHERE id IN ({q})",
            (1 if archived else 0, *ids))
        self.db.conn.commit()
        return cur.rowcount

    @Slot(int, int, result="QVariant")
    def archivedPhotos(self, offset: int = 0, limit: int = 500) -> list[dict]:
        """归档视图：仅返回 archived=1 的照片（按时间倒序分页）。"""
        rows = self.db.conn.execute(
            " SELECT id, thumbnail_path, file_name, taken_at, face_count, has_text,"
            " camera_model, file_path, width, height, rating, flag, color_label FROM photos"
            " WHERE status != 'missing' AND archived = 1"
            " ORDER BY sort_key DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return self._pack(rows)

    @Slot(int, int, int, result="QVariant")
    def ratedPhotos(self, min_rating: int = 1, offset: int = 0,
                    limit: int = 500) -> list[dict]:
        """评级 ≥ min_rating 的照片（min_rating=0 表示全部已评级）。"""
        where = "rating >= ?" if min_rating > 0 else "rating > 0"
        return self._pack(self._photo_rows(where, (min_rating,)
                                           if min_rating > 0 else (), limit, offset))

    @Slot(result=int)
    @Slot(int, result=int)
    def ratedCount(self, min_rating: int = 1) -> int:
        if min_rating > 0:
            return self.db.conn.execute(
                "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND rating >= ?",
                (min_rating,),
            ).fetchone()[0]
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND rating > 0"
        ).fetchone()[0]

    @Slot(str, int, int, result="QVariant")
    def flagPhotos(self, flag: str, offset: int = 0, limit: int = 500) -> list[dict]:
        """按旗标取照片：flag='pick'/'reject'/'none'。"""
        if flag == "none":
            where = "(flag = '' OR flag IS NULL)"
            return self._pack(self._photo_rows(where, (), limit, offset))
        return self._pack(self._photo_rows("flag = ?", (flag,), limit, offset))

    @Slot(str, result=int)
    def flagCount(self, flag: str) -> int:
        if flag == "none":
            return self.db.conn.execute(
                "SELECT COUNT(*) FROM photos WHERE status != 'missing'"
                " AND (flag = '' OR flag IS NULL)"
            ).fetchone()[0]
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND flag = ?",
            (flag,),
        ).fetchone()[0]

    # ---------- 批量时间校正（相机时钟/时区偏差） ----------
    @Slot(float, result="QVariant")
    @Slot(float, str, result="QVariant")
    def timeShiftPreview(self, hours: float, folder: str = "") -> dict:
        """预览：返回将受影响的照片数（不修改数据）。folder 为空=整库。"""
        if folder:
            n = self.db.conn.execute(
                "SELECT COUNT(*) FROM photos WHERE status != 'missing'"
                " AND taken_at IS NOT NULL AND taken_at != ''"
                " AND (folder_path = ? OR folder_path LIKE ? ESCAPE '\\')",
                (folder, folder + "/%"),
            ).fetchone()[0]
        else:
            n = self.db.conn.execute(
                "SELECT COUNT(*) FROM photos WHERE status != 'missing'"
                " AND taken_at IS NOT NULL AND taken_at != ''"
            ).fetchone()[0]
        return {"affected": n, "hours": hours}

    @Slot(float, result=int)
    @Slot(float, str, result=int)
    def timeShift(self, hours: float, folder: str = "") -> int:
        """按小时偏移拍摄时间（同步更新 taken_at 与 sort_key）。folder 为空=整库。"""
        import datetime

        conn = self.db.conn
        delta = datetime.timedelta(hours=float(hours))
        try:
            conn.execute("BEGIN")
            if folder:
                rows = conn.execute(
                    "SELECT id, taken_at FROM photos WHERE status != 'missing'"
                    " AND taken_at IS NOT NULL AND taken_at != ''"
                    " AND (folder_path = ? OR folder_path LIKE ? ESCAPE '\\')",
                    (folder, folder + "/%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, taken_at FROM photos WHERE status != 'missing'"
                    " AND taken_at IS NOT NULL AND taken_at != ''"
                ).fetchall()
            for pid, taken in rows:
                try:
                    dt = datetime.datetime.fromisoformat(taken)
                except ValueError:
                    continue
                ndt = dt + delta
                nts = ndt.isoformat(sep="T")
                conn.execute(
                    "UPDATE photos SET taken_at=?, sort_key=? WHERE id=?",
                    (nts, nts, pid),
                )
            conn.commit()
            return len(rows)
        except Exception:
            conn.rollback()
            log.exception("时间校正失败")
            return 0

    # ---------- 重计算任务（后台线程 + 进度信号） ----------
    def _spawn(self, kind: str, title: str, fn, args=()) -> bool:
        """后台任务互斥：已有任务运行时拒绝新任务（避免并发重复处理与写库竞争）。"""
        with self._busy_lock:
            if self._busy > 0:
                self._finish(_tr("{p1}已取消：有任务正在运行，请稍候").format(p1=title))
                return False
            self._busy = 1
        self.message.emit(_tr("正在{p1}…").format(p1=title))
        self.busyChanged.emit()
        # 0.5.53：手动任务也进队列广播（单阶段：共 1 项、当前第 1 项）
        self.chainProgress.emit(0, 1, json.dumps([title], ensure_ascii=False))
        self.chainProgress.emit(1, 1, json.dumps([title], ensure_ascii=False))
        self.chainProgress.emit(1, 1, json.dumps([title], ensure_ascii=False))

        # 0.6.8：3 秒心跳——弱机批量分析时计数可能几分钟不动（如语义向量
        # 按批编码），心跳持续刷新"已运行/预计剩余"，避免被误认为死机
        # （麒麟真机实测反馈）。fn 由 _run_with_progress 包裹时携带 state。
        state = getattr(fn, "progress_state", None)
        self._hb_state = state
        if not hasattr(self, "_hb_timer"):
            self._hb_timer = QTimer(self)
            self._hb_timer.setInterval(3000)
            self._hb_timer.timeout.connect(self._heartbeat_tick)
        if state is not None:
            self._hb_timer.start()

        def worker():
            try:
                stats = fn(*args)
                self._summarize(kind, stats)
            except Exception as e:
                log.exception("%s 失败", title)
                self._finish(_tr("{p1}失败：{p2}").format(p1=title, p2=e))
            finally:
                self._release_busy()
                self.photosChanged.emit()

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _heartbeat_tick(self) -> None:
        """0.6.8：3 秒心跳——计数不动也持续刷新（已耗时/预计剩余）。"""
        state = getattr(self, "_hb_state", None)
        if not state:
            self._hb_timer.stop()
            return
        import time as _time

        done = state["done"]
        tick = state.get("tick")
        if callable(tick):
            try:
                done = max(done, int(tick()))
            except Exception:
                pass
        if state["total"]:
            done = min(done, state["total"])
        elapsed = int(_time.monotonic() - state["t0"])
        label = self._progress_label(state)
        extra = _tr("已运行 {p1}").format(p1=f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        self.taskProgress.emit(done, state["total"],
                               (label + " · " + extra) if label else extra)

    def _progress_label(self, state) -> str:
        """阶段标签 + 预计剩余时间（按最近 90 秒滑动速率估算）。"""
        parts = [state["stage"]]
        samples = state["samples"]
        if len(samples) >= 2 and state["total"]:
            (ta, da), (tb, db) = samples[0], samples[-1]
            rate = (db - da) / max(tb - ta, 0.001)
            if rate > 0.001 and state["total"] > db:
                rem = int((state["total"] - db) / rate)
                parts.append(_tr("预计剩余 {p1}").format(
                    p1=f"{rem // 60:02d}:{rem % 60:02d}"))
        return " · ".join(p for p in parts if p)

    def _summarize(self, kind: str, stats: dict) -> None:
        if kind == "faces":
            msg = (
                _tr("人脸检测完成：扫描 {p1} 张，").format(p1=stats.get('scanned', 0))
                + _tr("检出 {p1} 张含人脸（共").format(p1=stats.get('with_faces', 0))
                + _tr(" {p1} 张脸），失败 {p2}").format(p1=stats.get('faces', 0), p2=stats.get('failed', 0))
            )
            cl = stats.get("cluster") or {}
            if cl.get("persons"):
                msg += _tr("；已自动聚类为 {p1} 位人物（人物页可重命名）").format(p1=cl['persons'])
            self._finish(msg)
        elif kind == "ocr":
            self._finish(
                _tr("OCR 完成：识别 {p1} 张，").format(p1=stats.get('scanned', 0))
                + _tr("{p1} 张含文字（{p2} 段）").format(p1=stats.get('with_text', 0), p2=stats.get('texts', 0))
            )
        elif kind == "hashes":
            hash_msg = _tr("感知哈希完成：计算 {p1} 张").format(p1=stats.get('ok', 0))
            if stats.get("fail"):
                hash_msg += _tr("，失败 {p1}").format(p1=stats['fail'])
            self._finish(hash_msg)
        elif kind == "events":
            self._finish(_tr("事件聚类完成：生成 {p1} 个事件").format(p1=stats.get('events', 0)))
        elif kind == "facecluster":
            self._finish(_tr("人脸聚类完成：{p1} 位人物").format(p1=stats.get('persons', 0)))
        elif kind == "reindex":
            self._finish(
                _tr("索引检查完成：共检查 {p1} 张，").format(p1=stats.get('checked', 0))
                + _tr("{p1} 张已在系统外被删除，已从搜索与归类中排除").format(p1=stats.get('missing', 0))
            )
        elif kind == "autotag":
            self._finish(
                _tr("自动打标签完成：新增 {p1} 条场景标签").format(p1=stats.get('added', 0))
            )
            self.photosChanged.emit()
        elif kind == "clip":
            if stats.get("no_model"):
                self._finish(_tr("语义向量未生成：缺少 Chinese-CLIP 模型组件（models/clip/），"
                                 "其余功能不受影响"))
                return
            clip_msg = (
                _tr("语义向量完成：生成 {p1} 张；").format(p1=stats.get('vectors', 0))
                + _tr("场景标签新增 {p1} 个").format(p1=stats.get('tags', 0))
                + (_tr("（用时 {p1} 秒）").format(p1=stats.get('seconds', 0)) if stats.get("seconds") else "")
            )
            if stats.get("vec_fail"):
                clip_msg = (
                    _tr("语义向量完成：生成 {p1} 张，").format(p1=stats.get('vectors', 0))
                    + _tr("失败 {p1} 张；场景标签新增 {p2} 个").format(p1=stats['vec_fail'], p2=stats.get('tags', 0))
                    + (_tr("（用时 {p1} 秒）").format(p1=stats.get('seconds', 0)) if stats.get("seconds") else "")
                )
            self._finish(clip_msg)
        elif kind == "deepdecode":
            pass  # 消息已在任务内 _finish，这里仅占位
        elif kind == "scene_suggest":
            import json as _json

            self.sceneSuggestionsFinished.emit(_json.dumps(stats, ensure_ascii=False))
            if stats.get("ok"):
                self._finish(
                    _tr("场景建议完成：扫描 {p1} 张，").format(p1=stats.get('scanned', 0))
                    + _tr("未覆盖 {p1} 张，").format(p1=stats.get('uncovered', 0))
                    + _tr("建议 {p1} 个新词（请在列表中勾选确认）").format(p1=len(stats.get('suggestions') or []))
                )
            else:
                self._finish(_tr("场景建议不可用：{p1}").format(p1=stats.get('reason', 'unknown')))

    @Slot(int, result=str)
    def runFaces(self, limit: int = 0) -> str:
        from photo_manager.core.faces import FacePipeline

        def task(prog):
            stats = FacePipeline(self.db, models_dir()).run(
                limit=limit or None,
                workers=self._analysis_workers(),
                progress_cb=lambda done, total, path: prog(done, total)
            )
            # 检测后自动聚类（与自动分析链行为一致）
            from photo_manager.core.facecluster import FaceClusterer

            stats["cluster"] = FaceClusterer(self.db, threshold=self.faceClusterThreshold()).run()
            return stats

        self._spawn("faces", "人脸检测", self._run_with_progress(task, "人脸检测"))
        return ""

    @Slot(int, result=str)
    def runOcr(self, limit: int = 0) -> str:
        from photo_manager.core.ocr import OCRPipeline

        def task(prog):
            return OCRPipeline(self.db).run(
                limit=limit or None,
                workers=self._analysis_workers(),
                progress_cb=lambda done, total, path: prog(done, total)
            )

        self._spawn("ocr", "文字识别", self._run_with_progress(task, "文字识别"))
        return ""

    @Slot(int, result=str)
    def runHashes(self, limit: int = 0) -> str:
        from photo_manager.core.duplicates import DuplicateScanner

        def task(prog):
            return DuplicateScanner(self.db).compute_hashes(
                limit=limit or None,
                workers=self._analysis_workers(),
                progress_cb=lambda done, total: prog(done, total)
            )

        self._spawn("hashes", "哈希计算", self._run_with_progress(task, "哈希计算"))
        return ""

    @Slot(result=str)
    def runEvents(self) -> str:
        from photo_manager.core.events import EventClusterer

        def task(prog):
            return EventClusterer(self.db).run(progress_cb=prog)

        self._spawn("events", "事件聚类", self._run_with_progress(task, "事件聚类"))
        return ""

    @Slot(result=str)
    def runFaceCluster(self) -> str:
        from photo_manager.core.facecluster import FaceClusterer

        def task(prog):
            return FaceClusterer(self.db, threshold=self.faceClusterThreshold()).run(
                progress_cb=lambda done, total: prog(done, total)
            )

        self._spawn("facecluster", "人脸聚类", self._run_with_progress(task, "人脸聚类"))
        return ""

    @Slot(result=bool)
    def clipAvailable(self) -> bool:
        """Chinese-CLIP 模型组件是否就位（供 UI 显隐语义功能与提示）。"""
        from photo_manager.core.clip import get_service

        return get_service().available

    @Slot(result=bool)
    def clipAutoIndexEnabled(self) -> bool:
        """设置项：扫描入库后是否自动为无向量照片生成 CLIP 语义向量（0.5.46 默认开）。

        返回进程内真值 self._clip_auto（启动时从 QSettings 读入），确保同会话内
        读取与设置一致，不受 QSettings 跨实例缓存影响。
        """
        return getattr(self, "_clip_auto", True)

    @Slot(bool)
    def setClipAutoIndexEnabled(self, on: bool) -> None:
        from PySide6.QtCore import QSettings

        on = bool(on)
        self._clip_auto = on
        qs = QSettings("PhotoManager", "PhotoManager")
        qs.setValue("clipAutoIndex", on)
        qs.sync()  # 持久化，供下次启动读入
        self.clipAutoIndexChanged.emit(on)
        # 0.5.49：开启时立即为「已有照片」增量补跑一次向量——用户预期"开了就生效"，
        # 此前只有下次扫描入库才触发，存量照片永远不出向量（繁忙时挂起，链尾接续）
        if on:
            self._maybe_auto_clip()

    # ---------- 开机自启 / 关闭到托盘（0.5.48） ----------
    @Slot(result=bool)
    def autoStartEnabled(self) -> bool:
        """开机自启（默认关）。进程内单一真值 self._auto_start。"""
        return getattr(self, "_auto_start", False)

    # ---------- 界面语言（0.5.66 多语言：语言包见 ui/qml/i18n/） ----------
    @Slot(result=str)
    def uiLang(self) -> str:
        from PySide6.QtCore import QSettings

        return str(QSettings("PhotoManager", "PhotoManager")
                   .value("ui/lang", "zh", type=str))

    @Slot(str, result=str)
    def i18nCatalog(self, code: str) -> str:
        """返回语言包 JSON 文本（QML XHR 读本地文件受限，经桥接读取）。

        0.6.2：支持用户自装语言包——查找顺序：数据目录 i18n/ 优先，
        其次内置 QML_DIR/i18n/。用户包放 <数据库目录>/i18n/<code>.json。
        """
        from pathlib import Path

        from photo_manager import QML_DIR

        bases = [Path(self.db.path).resolve().parent / "i18n",
                 QML_DIR / "i18n"]
        for base in bases:
            p = base / f"{code}.json"
            if p.exists():
                try:
                    return p.read_text(encoding="utf-8")
                except OSError:
                    continue
        return "{}"

    @Slot(result=str)
    def i18nLanguages(self) -> str:
        """列出可用语言：[{code, name}]（0.6.2，供语言切换菜单）。

        中文为源语言永远在列；其余 = 内置包 + 数据目录 i18n/ 用户包。
        语言显示名取包内 "_name" 键（语言包自声明，如 "English"/"Français"）。
        """
        import json as _json
        from pathlib import Path

        from photo_manager import QML_DIR

        langs = [{"code": "zh", "name": "中文"}]
        seen = {"zh"}
        bases = [QML_DIR / "i18n",
                 Path(self.db.path).resolve().parent / "i18n"]
        for base in bases:
            if not base.is_dir():
                continue
            for p in sorted(base.glob("*.json")):
                code = p.stem
                if code in seen:
                    continue
                name = code
                try:
                    head = _json.loads(p.read_text(encoding="utf-8"))
                    name = str(head.get("_name") or code)
                    seen.add(code)
                except Exception:  # noqa: BLE001 — 损坏包跳过
                    continue
                langs.append({"code": code, "name": name})
        return _json.dumps(langs)

    @Slot(str)
    def setUiLang(self, code: str) -> None:
        from PySide6.QtCore import QSettings

        from photo_manager.i18n import set_lang

        qs = QSettings("PhotoManager", "PhotoManager")
        qs.setValue("ui/lang", code)
        qs.sync()
        set_lang(code)

    # ---------- 首次运行引导（0.5.53） ----------
    @Slot(result=bool)
    def firstRunDone(self) -> bool:
        """首启引导是否已确认过（QSettings firstRunDone，永久 bool）。

        0.5.64 曾短暂改为按 APP_VERSION 记忆（每版本弹一次），
        用户反馈不需要——回归永久 bool：写过后不再自动弹出
        （帮助菜单仍可随时手动打开）。兼容读旧版本号字符串：
        QSettings type=bool 对非 "false"/空 值均转 True。
        """
        from PySide6.QtCore import QSettings

        return bool(QSettings("PhotoManager", "PhotoManager")
                    .value("firstRunDone", False, type=bool))

    @Slot()
    def setFirstRunDone(self) -> None:
        from PySide6.QtCore import QSettings

        qs = QSettings("PhotoManager", "PhotoManager")
        qs.setValue("firstRunDone", True)
        qs.sync()

    @Slot(bool)
    def setAutoStartEnabled(self, on: bool) -> None:
        from PySide6.QtCore import QSettings

        on = bool(on)
        if _autostart_apply(on):
            self._auto_start = on
            qs = QSettings("PhotoManager", "PhotoManager")
            qs.setValue("autoStart", on)
            qs.sync()
        # 无论成败都发信号：失败时回填当前真值，设置里的勾选自动回滚
        self.autoStartChanged.emit(self._auto_start)

    @Slot(result=bool)
    def startupMaximizedEnabled(self) -> bool:
        """启动时窗口最大化（0.5.67 新增，默认开）。进程内单一真值。"""
        return getattr(self, "_startup_maximized", True)

    @Slot(bool)
    def setStartupMaximizedEnabled(self, on: bool) -> None:
        from PySide6.QtCore import QSettings

        on = bool(on)
        self._startup_maximized = on
        qs = QSettings("PhotoManager", "PhotoManager")
        qs.setValue("ui/startMaximized", on)
        qs.sync()

    @Slot(result=bool)
    def trayEnabled(self) -> bool:
        """关闭窗口时最小化到托盘（默认开）。进程内单一真值 self._tray_enabled。"""
        return getattr(self, "_tray_enabled", True)

    @Slot(bool)
    def setTrayEnabled(self, on: bool) -> None:
        from PySide6.QtCore import QSettings

        on = bool(on)
        self._tray_enabled = on
        qs = QSettings("PhotoManager", "PhotoManager")
        qs.setValue("trayEnabled", on)
        qs.sync()
        self.trayEnabledChanged.emit(on)

    def _clip_pending_count(self) -> int:
        """尚无向量的照片/视频数（增量判定；0 则无需加载模型）。

        0.5.51：视频（有关键帧）也纳入计数——否则带视频的库永远判 0 待处理，
        启动补跑/挂起接续都会跳过视频。

        改独立只读短连接——本方法会被各任务 worker 的 finally
        （_release_busy→_drain_clip_pending）在工作线程调用，用共享
        self.db.conn 会与主线程 UI 查询并发触发 pysqlite 语句缓存竞态。
        """
        import sqlite3

        from photo_manager.core.clip import MODEL_ID

        conn = sqlite3.connect(self.db.path, timeout=30)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM photos p LEFT JOIN photo_embeddings e "
                "ON e.photo_id = p.id AND e.model = ? "
                "WHERE e.photo_id IS NULL"
                " AND (p.media_type='photo' OR p.media_type='video')",
                (MODEL_ID,)).fetchone()
        finally:
            conn.close()
        return int(row[0]) if row else 0

    def _release_busy(self) -> None:
        """释放任务互斥（0.5.50：唯一释放出口）。

        所有后台任务结束时都必须走这里（_spawn / 各 worker 的 finally），
        释放后顺手接续被挂起的自动语义索引——否则 _clip_pending 可能
        永无接续者（例：启动补跑撞上手动任务，向量再次静默丢失）。
        """
        with self._busy_lock:
            self._busy = 0
        hb = getattr(self, "_hb_timer", None)
        if hb is not None:
            hb.stop()
        self._drain_clip_pending()
        self._drain_ingest_queue()
        self.busyChanged.emit()

    def _drain_clip_pending(self) -> None:
        """_busy 已释放时消费挂起标志并触发 CLIP；仍繁忙则留给下一个释放者。"""
        with self._busy_lock:
            if not getattr(self, "_clip_pending", False) or self._busy > 0:
                return
            self._clip_pending = False
        self._maybe_auto_clip()

    def _maybe_auto_clip(self) -> None:
        """入库/分析完成后（或启动/开启开关时），若开启自动语义向量且模型就位，
        则在后台增量生成 CLIP 向量。

        0.5.49 修复（用户报"设置了自动索引但没有向量"）：
        ① 原先 _ingest_many_worker 里 _start_auto_chain() 之后无条件起 clip 线程，
           而 runClip 走 _spawn 互斥——自动分析链正占用 _busy，clip 每次都被拒
           （"有任务正在运行"），向量永远不生成。现改为：繁忙时挂起
           _clip_pending，由 _auto_chain_worker 结束（_busy 释放后）接续；
        ② 开启开关即触发一次（存量照片生效），且启动 10s 后按需补跑
           （老用户开关早已开着、却从未生成过向量的场景）。
        """
        try:
            if not self.clipAutoIndexEnabled() or not self.clipAvailable():
                self._clip_pending = False
                return
            if self._clip_pending_count() <= 0:
                self._clip_pending = False  # 无待处理照片：不白加载模型
                return
            with self._busy_lock:
                busy = self._busy > 0
            if busy:
                self._clip_pending = True  # 等分析链结束接续
                return
            self._clip_pending = False
            threading.Thread(target=self.runClip, daemon=True).start()
        except Exception:
            log.exception("自动语义向量触发失败")

    @Slot(result=str)
    def runClip(self) -> str:
        """生成语义向量 + CLIP 零样本场景标签（后台执行）。需 Chinese-CLIP 模型。

        不触碰原图、不删除任何数据；增量：只处理尚无向量的照片。
        """
        import numpy as np
        import time

        from photo_manager.core.clip import MODEL_ID, get_service
        from photo_manager.core import autotag

        svc = get_service()
        if not svc.available:
            self.message.emit(_tr("未检测到 Chinese-CLIP 模型组件，无法生成语义向量（应位于 models/clip/）"))
                # 0.5.64：返回规范 stats——此前 return "" 让 _summarize 对字符串
            # 调 .get() 抛 AttributeError，用户看到的是红色「语义向量失败：
            # 'str' object has no attribute 'get'」而非模型缺失提示
            return {"vectors": 0, "tags": 0, "no_model": True}

        # 0.5.27：自动链的 CLIP 打标用合并后的最终词表（内置∪自定义，「-词」排除），
        # 与工具中心"自动打标签"一致；在派发后台任务前读取，避免线程内再碰 QSettings。
        clip_tags = self.scene_vocab()

        def task(prog):
            # 0.5.58：编码与打标全部挪到无 Qt 的子进程（--clip-worker 模式，
            # subprocess 自调用）分片执行——Qt 6.11 环境下后台线程首次加载/运行
            # native 重库（rawpy/onnxruntime/libraw）会访问违例闪退（0.5.57
            # 用户报两次，向量恒为 0；纯脚本/主线程/独立子进程均正常）。
            # 每批一个子进程：子进程崩溃仅该批计失败，主进程不受影响。
            import json as _json
            import subprocess
            import tempfile as _tempfile

            from photo_manager.core.clip import MODEL_ID

            import sqlite3

            conn = sqlite3.connect(self.db.path, timeout=30)
            # 0.6.8：批内按张进度文件——子进程每编码一张覆写 {"done": n}，
            # 心跳定时器读取，进度数字按张刷新而非按批（弱机一批要等数分钟，
            # 麒麟实测被误认为卡死）
            _prog_tmpdir = _tempfile.mkdtemp(prefix="pmclip_prog_")
            prog_path = os.path.join(_prog_tmpdir, "prog.json")
            prog_state = getattr(prog, "progress_state", None)
            _base = {"i": 0}

            def _read_prog() -> int:
                try:
                    with open(prog_path, encoding="utf-8") as f:
                        return int(_json.load(f).get("done", 0))
                except Exception:
                    return 0
            if prog_state is not None:
                prog_state["tick"] = lambda: _base["i"] + _read_prog()
            try:
                rows = conn.execute(
                    "SELECT p.id, p.file_path, p.thumbnail_path, p.thumb_width,"
                    " p.thumb_height, p.media_type "
                    "FROM photos p LEFT JOIN photo_embeddings e"
                    " ON e.photo_id = p.id AND e.model = ? "
                    "WHERE e.photo_id IS NULL"
                    " AND (p.media_type='photo' OR p.media_type='video')"
                    " ORDER BY p.id", (MODEL_ID,)
                ).fetchall()
                # 视频关键帧（相对路径）按 photo_id 归组
                vframes: dict[int, list[str]] = {}
                for pid_, fp_ in conn.execute(
                        "SELECT photo_id, path FROM video_frames"
                        " ORDER BY photo_id, idx").fetchall():
                    vframes.setdefault(pid_, []).append(fp_)
                total = len(rows)
                prog(0, total)
                ok = fail = 0
                t0 = time.perf_counter()
                jobs = [(r[0], r[1], r[2], r[3], r[4],
                         vframes.get(r[0]) if (r[5] or "photo") == "video" else None)
                        for r in rows]
                BATCH = 16

                def _run_worker(mode, payload) -> dict:
                    """派发一个 --clip-worker 子进程（JSON 进/出），返回结果 dict。"""
                    tmpdir = _tempfile.mkdtemp(prefix="pmclip_")
                    jf = os.path.join(tmpdir, "jobs.json")
                    of = os.path.join(tmpdir, "out.json")
                    with open(jf, "w", encoding="utf-8") as f:
                        _json.dump(payload, f, ensure_ascii=False)
                    try:
                        # 打包版：exe 自调用；开发版：python -m photo_manager.main
                        if getattr(sys, "frozen", False):
                            cmd = [sys.executable, "--clip-worker",
                                   self.db.path, jf, of, mode]
                        else:
                            cmd = [sys.executable, "-m", "photo_manager.main",
                                   "--clip-worker", self.db.path, jf, of, mode]
                        if mode == "encode":
                            cmd.append(prog_path)  # 0.6.8 批内按张进度文件
                        subprocess.run(
                            cmd, timeout=900, check=False,
                            creationflags=(0x08000000 if os.name == "nt" else 0))
                    finally:
                        try:
                            if os.path.exists(of):
                                with open(of, encoding="utf-8") as f:
                                    return _json.load(f)
                        except Exception:
                            log.exception("clip 子进程结果读取失败")
                        finally:
                            shutil.rmtree(tmpdir, ignore_errors=True)
                    return {"ok": 0, "fail": len(payload), "tags": 0}

                import base64

                import numpy as np

                for i in range(0, len(jobs), BATCH):
                    batch = jobs[i:i + BATCH]
                    try:
                        if prog_state is not None:
                            _base["i"] = i
                            if os.path.exists(prog_path):
                                os.remove(prog_path)
                        st = _run_worker("encode", batch)
                        ok += st.get("ok", 0)
                        fail += st.get("fail", 0) + (
                            len(batch) - st.get("ok", 0) - st.get("fail", 0))
                        # 向量由主进程写库（0.5.58：子进程不碰库，
                        # 规避"子进程写库+主进程 sqlite mmap 并发"崩溃）
                        for pid, b64, model, dim in st.get("vectors", []):
                            conn.execute(
                                "INSERT INTO photo_embeddings(photo_id, embedding,"
                                " model, dim) VALUES (?,?,?,?)"
                                " ON CONFLICT(photo_id) DO UPDATE SET"
                                " embedding=excluded.embedding, model=excluded.model,"
                                " dim=excluded.dim, created_at=datetime('now')",
                                (pid, base64.b64decode(b64), model, dim))
                        conn.commit()
                    except Exception:
                        log.exception("clip 子进程批次失败（%d 张计为失败）", len(batch))
                        fail += len(batch)
                    prog(min(i + BATCH, total), total)

                # 场景标签：文本向量同样在子进程内编码
                tag_stats = {"added": 0}
                if total > 0:
                    try:
                        tag_stats = _run_worker("autotag", clip_tags)
                    except Exception:
                        log.exception("clip 场景标签子进程失败")
                el = time.perf_counter() - t0
                return {
                    "vectors": ok,
                    "vec_fail": fail,
                    "tags": tag_stats.get("added", 0),
                    "seconds": round(el),
                }
            finally:
                conn.close()
                shutil.rmtree(_prog_tmpdir, ignore_errors=True)

        self._spawn("clip", "语义向量", self._run_with_progress(task, "语义向量"))
        return ""

    def _run_with_progress(self, task, stage: str = ""):
        """把 task(fn) 包成无进度回调的调用（进度通过 taskProgress 信号上报）。

        0.6.6：stage 为任务名（与 _spawn 的 title 一致），随进度信号上报——
        此前标签恒为空串，底部进度弹窗只显示数字不显示正在跑什么任务
        （用户反馈：语义向量任务"没有显示正在后台执行什么任务"）。
        0.6.8：state 挂到返回的 run.progress_state 供 _spawn 心跳定时器
        读取——弱机上计数长期不动时心跳仍每 3 秒刷新（已耗时/预计剩余），
        避免被误认为死机；clip 任务通过 state["tick"] 提供批内按张计数。"""
        import time as _time

        state = {"stage": stage, "done": 0, "total": 0,
                 "t0": _time.monotonic(), "samples": [], "tick": None}

        def prog(done, total):
            state["done"] = done or 0
            state["total"] = total or 0
            now = _time.monotonic()
            state["samples"] = [(t, d) for t, d in state["samples"]
                                if now - t <= 90][-16:]
            state["samples"].append((now, state["done"]))
            self.taskProgress.emit(state["done"], state["total"],
                                   self._progress_label(state))

        def run(*_a):
            # 0.6.11 修复：必须把 prog（回调）而非 run（包装器自己）传给
            # task——0.6.8 起误传 run 导致 task 首次调 prog 时重新执行
            # 整个任务，无限自递归（"语义向量失败：递归超限"，所有
            # _spawn 任务同病）。
            return task(prog)

        prog.progress_state = state   # 供 clip 任务挂 tick
        run.progress_state = state    # 供 _spawn 心跳定时器读取
        return run

    # ---------- 自动分析链：扫描入库后按 轻量→人脸→OCR 顺序自动执行 ----------
    ANALYSIS_LABELS = [
        ("events", "事件聚类"),
        ("hashes", "重复检测"),
        ("faces", "人脸检测"),
        ("ocr", "文字识别"),
    ]

    @Slot(result="QVariant")
    def analysisStatus(self) -> list[dict]:
        """各分析阶段完成情况（供工具中心展示与测试断言）。"""
        conn = self.db.conn
        total = self._photo_count()
        done_at = {
            r[0]: r[1] for r in conn.execute(
                "SELECT stage, total_at_time FROM analysis_state"
            ).fetchall()
        }
        faces_p = conn.execute(
            "SELECT COUNT(*) FROM photos WHERE face_done=0 AND status='indexed'"
        ).fetchone()[0]
        ocr_p = conn.execute(
            "SELECT COUNT(*) FROM photos WHERE ocr_done=0 AND status='indexed'"
        ).fetchone()[0]
        out = []
        for key, label in self.ANALYSIS_LABELS:
            if key in ("events", "hashes"):
                done = done_at.get(key) == total
            elif key == "faces":
                done = faces_p == 0
            else:
                done = ocr_p == 0
            out.append({"stage": label, "done": done})
        return out

    def _pending_stages(self) -> list[tuple[str, str]]:
        """按顺序返回需要执行的阶段（已完成的跳过，中断后可续跑）。"""
        conn = self.db.conn
        total = self._photo_count()
        done_at = {
            r[0]: r[1] for r in conn.execute(
                "SELECT stage, total_at_time FROM analysis_state"
            ).fetchall()
        }
        pending = []
        if done_at.get("events") != total:
            pending.append(("events", "事件聚类"))
        if done_at.get("hashes") != total:
            pending.append(("hashes", "重复检测"))
        faces_p = conn.execute(
            "SELECT COUNT(*) FROM photos WHERE face_done=0 AND status='indexed'"
        ).fetchone()[0]
        if faces_p:
            pending.append(("faces", "人脸检测"))
        ocr_p = conn.execute(
            "SELECT COUNT(*) FROM photos WHERE ocr_done=0 AND status='indexed'"
        ).fetchone()[0]
        if ocr_p:
            pending.append(("ocr", "文字识别"))
        return pending

    @Slot(result=str)
    def autoAnalyze(self) -> str:
        """开始/继续自动分析链（events→hashes→faces→ocr）。"""
        self._start_auto_chain()
        return ""

    @Slot(result=str)
    def stopAnalysis(self) -> str:
        """请求中断当前分析链：当前阶段处理完一张后停下，已完成阶段保留。"""
        self._cancel.set()
        self.message.emit(_tr("正在停止分析…（当前照片处理完即停，已完成阶段会保留）"))
        return ""

    def _start_auto_chain(self) -> bool:
        with self._busy_lock:
            if self._busy > 0:
                self._finish("分析未开始：有任务正在运行，请稍候")
                return False
            self._busy = 1
        self._cancel.clear()
        threading.Thread(target=self._auto_chain_worker, daemon=True).start()
        return True

    def _auto_chain_worker(self) -> None:
        try:
            stages = self._pending_stages()
            if not stages:
                self._finish("分析无需运行：事件、重复、人脸、文字均为最新")
                return
            n = len(stages)
            # 0.5.53：任务队列广播（进度弹窗显示"共 N 项/当前第 i 项"列表）
            self.chainProgress.emit(
                0, n, json.dumps([lb for _, lb in stages], ensure_ascii=False))
            for i, (key, label) in enumerate(stages, 1):
                if self._cancel.is_set():
                    self._finish(
                        _tr("分析已中断：已完成 {p1}/{p2} 个阶段，").format(p1=i - 1, p2=n)
                        + _tr("可稍后在工具中心点「自动分析」继续")
                    )
                    return
                self.chainProgress.emit(
                    i, n, json.dumps([lb for _, lb in stages], ensure_ascii=False))
                self.message.emit(_tr("自动分析 {p1}/{p2}：{p3}…").format(p1=i, p2=n, p3=label))
                self._run_stage(key, label)
        except Exception:
            log.exception("自动分析失败")
            self._finish(_tr("自动分析失败：{p1}").format(p1=sys.exc_info()[1]))
        finally:
            # _release_busy 内部会接续被挂起的自动语义索引（0.5.49/0.5.50：
            # clip 曾与链争 _busy 互斥必败，导致"开了自动索引却永远不出向量"）
            self._release_busy()
            self._cancel.clear()
            self.photosChanged.emit()

    def _photo_count(self) -> int:
        """photos 总行数（独立短连接读取）。

        分析链在 worker 线程执行 `SELECT COUNT(*) FROM photos` 时，QML 主线程
        （analysisStatus 等槽）会用共享连接并发执行**同一条 SQL**：pysqlite 的
        语句缓存不防这种并发，两个线程可能拿到同一条预编译语句互相 reset，
        fetchone() 会返回 None（threadsafety=3 下仍可 10 秒内复现数百次），
        曾致自动分析链「重复检测」阶段崩溃。独立连接无共享语句缓存，天然规避。
        """
        import sqlite3

        conn = sqlite3.connect(self.db.path, timeout=10)
        try:
            row = conn.execute("SELECT COUNT(*) FROM photos").fetchone()
            return int(row[0]) if row else 0
        except Exception:
            log.warning("photo count 读取失败", exc_info=True)
            return 0
        finally:
            conn.close()

    def _run_stage(self, key: str, label: str) -> None:
        conn = self.db.conn
        total = self._photo_count()
        cancel = self._cancel.is_set
        try:
            if key == "events":
                from photo_manager.core.events import EventClusterer

                stats = EventClusterer(self.db).run(
                    progress_cb=lambda d, t: self.taskProgress.emit(d, t, label),
                    cancel=cancel,
                )
                msg = _tr("{p1}完成：生成 {p2} 个事件").format(p1=label, p2=stats.get('events', 0))
            elif key == "hashes":
                from photo_manager.core.duplicates import DuplicateScanner

                stats = DuplicateScanner(self.db).compute_hashes(
                    workers=self._analysis_workers(),
                    progress_cb=lambda d, t: self.taskProgress.emit(d, t, label),
                    cancel=cancel,
                )
                msg = _tr("{p1}完成：计算 {p2} 张").format(p1=label, p2=stats.get('ok', 0))
                if stats.get("fail"):
                    msg += _tr("，失败 {p1}").format(p1=stats['fail'])
            elif key == "faces":
                from photo_manager.core.faces import FacePipeline

                stats = FacePipeline(self.db, models_dir()).run(
                    workers=self._analysis_workers(),
                    progress_cb=lambda d, t, p: self.taskProgress.emit(
                        d, t, f"{label}|{p}" if p else label),
                    cancel=cancel,
                )
                msg = _tr("{p1}完成：扫描 {p2} 张，检出 {p3} 张含人脸").format(p1=label, p2=stats.get('scanned', 0), p3=stats.get('with_faces', 0))
                # 检测后自动聚类：人物页直接按"人物 1/2/…"编号列出，无需手动再点
                if not cancel():
                    from photo_manager.core.facecluster import FaceClusterer

                    cl = FaceClusterer(self.db, threshold=self.faceClusterThreshold()).run(
                        progress_cb=lambda d, t: self.taskProgress.emit(
                            d, t, "人脸聚类"))
                    stats["cluster"] = cl
                    if cl.get("persons"):
                        msg += _tr("；自动聚类为 {p1} 位人物").format(p1=cl['persons'])
            elif key == "ocr":
                from photo_manager.core.ocr import OCRPipeline

                stats = OCRPipeline(self.db).run(
                    workers=self._analysis_workers(),
                    progress_cb=lambda d, t, p: self.taskProgress.emit(
                        d, t, f"{label}|{p}" if p else label),
                    cancel=cancel,
                )
                msg = _tr("{p1}完成：识别 {p2} 张，{p3} 张含文字").format(p1=label, p2=stats.get('scanned', 0), p3=stats.get('with_text', 0))
            else:
                return
            if not self._cancel.is_set():
                conn.execute(
                    "INSERT OR REPLACE INTO analysis_state(stage, finished_at, total_at_time)"
                    " VALUES (?, datetime('now'), ?)",
                    (key, total),
                )
                conn.commit()
                self._finish(msg)
        except Exception as e:
            log.exception("%s 失败", label)
            hint = ""
            if key in ("faces", "ocr"):
                if isinstance(e, BrokenProcessPool):
                    hint = "（后台识别进程启动失败，已自动改用单进程重试；仍失败则多为内存不足）"
                else:
                    hint = "（多为个别图片文件损坏或路径失效；识别其余照片不受影响，可在工具中心重试）"
            self._finish(_tr("{p1}失败：{p2}{p3}").format(p1=label, p2=e, p3=hint))

    @Slot(str, str, result=int)
    def bulkTag(self, match: str, tag: str) -> int:
        """按路径模糊匹配批量打标签（等价 CLI `pm tag`）。"""
        match, tag = match.strip(), tag.strip()
        if not match or not tag:
            return 0
        from photo_manager.core.search import _like_escape

        rows = self.db.conn.execute(
            "SELECT id FROM photos WHERE file_path LIKE ? ESCAPE '\\'",
            (f"%{_like_escape(match)}%",),
        ).fetchall()
        n = 0
        for (pid,) in rows:
            self.db.conn.execute(
                "INSERT INTO photo_tags(photo_id, tag) VALUES (?,?) "
                "ON CONFLICT(photo_id, tag) DO NOTHING",
                (pid, tag),
            )
            n += 1
        self.db.conn.commit()
        self.photosChanged.emit()
        return n

    @Slot("QVariant", str, result=int)
    def batchTag(self, ids, tag: str) -> int:
        """对指定照片 ID 批量打标签；单事务，任一失败即整体回滚。"""
        from PySide6.QtQml import QJSValue

        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        ids = [int(i) for i in (ids or [])]
        tag = (tag or "").strip()
        if not ids or not tag:
            return 0
        conn = self.db.conn
        try:
            conn.execute("BEGIN")
            cur = conn.executemany(
                "INSERT INTO photo_tags(photo_id, tag) VALUES (?, ?) "
                "ON CONFLICT(photo_id, tag) DO NOTHING",
                [(pid, tag) for pid in ids],
            )
            conn.commit()
            n = cur.rowcount
        except Exception:
            conn.rollback()
            log.exception("batchTag 失败")
            return 0
        return n

    @Slot(str)
    def setClipboard(self, text: str) -> None:
        """把文本写入系统剪贴板。"""
        try:
            from PySide6.QtGui import QGuiApplication

            QGuiApplication.clipboard().setText(text or "")
        except Exception:
            log.exception("写剪贴板失败")

    @Slot(str, str, result=int)
    def moveTag(self, src: str, dst_parent: str) -> int:
        """把标签节点 src（**含其子孙**）移动到 dst_parent 下。

        例：moveTag("北京", "旅行/国内") → 北京→旅行/国内/北京，且 北京/朝阳区
        连带变成 旅行/国内/北京/朝阳区。dst_parent 为空表示移到顶层。
        :return: 迁移的标签记录数；**-1 表示非法**（不能移到自身或自身子孙下）。
        """
        src = (src or "").strip().strip("/")
        dst_parent = (dst_parent or "").strip().strip("/")
        if not src:
            return 0
        # 循环校验：把父节点拖进自己的子孙会形成环
        if dst_parent == src or dst_parent.startswith(src + "/"):
            return -1
        name = src.rsplit("/", 1)[-1]
        new_path = f"{dst_parent}/{name}" if dst_parent else name
        if new_path == src:
            return 0
        return self._rename_tag(src, new_path)

    @Slot("QVariant", str, result=int)
    def moveTagsBatch(self, paths, dst_parent: str) -> int:
        """批量把若干标签节点归入 dst_parent 下（各自含子孙，跳过非法项）。"""
        total = 0
        for p in (paths or []):
            r = self.moveTag(str(p), dst_parent)
            if r > 0:
                total += r
        return total

    # ---------- 场景识别词表（可配置） ----------
    @Slot(result=str)
    def sceneTags(self) -> str:
        """用户自定义场景词表（逗号/换行分隔）；空串表示用内置默认词表。"""
        from PySide6.QtCore import QSettings
        v = QSettings("PhotoManager", "PhotoManager").value("sceneTags", "")
        return str(v) if v else ""

    @Slot(str)
    def setSceneTags(self, text: str) -> None:
        from PySide6.QtCore import QSettings
        QSettings("PhotoManager", "PhotoManager").setValue("sceneTags", text or "")

    @Slot(result=str)
    def autoTagAll(self) -> str:
        """场景自动打标签（后台线程，幂等）。结果见 message 信号。"""
        from photo_manager.core.autotag import auto_tag_library

        def work():
            return auto_tag_library(self.db, tags=self.scene_vocab())

        self._spawn("autotag", "自动打标签", work)
        return ""

    def scene_vocab(self) -> list:
        """最终场景词表（0.5.27 追加合并语义：内置 ∪ 自定义，「-词」排除内置）。

        自动分析链与工具中心共用；在派发后台任务前调用，避免线程内碰 QSettings。
        """
        from photo_manager.core.autotag import resolve_scene_vocab

        return resolve_scene_vocab(self.sceneTags())

    @Slot(result=str)
    def sceneSuggestions(self) -> str:
        """分析词表未覆盖的场景簇并建议新词（后台执行，只读不写库）。

        结果经 sceneSuggestionsFinished(JSON) 信号返回；采纳与否由用户勾选确认。
        """
        from photo_manager.core import scene_suggest

        def work():
            return scene_suggest.suggest_scenes(self.db, vocab=self.scene_vocab())

        self._spawn("scene_suggest", "场景建议分析", work)
        return ""

    @Slot(str, result=str)
    def applySceneSuggestions(self, words: str) -> str:
        """把勾选采纳的场景词写入设置中的自定义词表（追加合并语义，幂等去重）。

        若某词此前被「-词」排除，勾选采纳视为推翻排除（移除排除项并加入）。
        返回实际新加入的词数。
        """
        from photo_manager.core.autotag import merge_custom_words

        text, n = merge_custom_words(self.sceneTags(),
                                     str(words or "").replace("\n", ",").split(","))
        if n:
            self.setSceneTags(text)
        return str(n)

    @Slot(str, result=str)
    def restoreBackup(self, backup_file: str) -> str:
        """从备份恢复数据库：先备份现状 → 关连接 → 恢复 → 重连（后台线程）。"""
        from photo_manager.core.backup import backup_db, restore_db

        with self._busy_lock:
            if self._busy > 0:
                self._finish("后台任务运行中，请等待完成后再恢复")
                return ""
            self._busy = 1
        self.message.emit(_tr("正在从备份恢复…"))
        def worker():
            try:
                self.db.close()
                backup_db(self.db, Path(self.db.path).parent / "backups")
                restore_db(self.db.path, backup_file)
                self.db = Database(self.db.path).connect()
                self.search = PhotoSearch(self.db)
                self._finish(_tr("已从备份恢复：{p1}").format(p1=backup_file))
                self.photosChanged.emit()
            except Exception as e:
                log.exception("恢复失败")
                try:
                    if self.db.conn is None:
                        self.db = Database(self.db.path).connect()
                        self.search = PhotoSearch(self.db)
                except Exception:
                    pass
                self._finish(_tr("恢复失败：{p1}").format(p1=e))
            finally:
                self._release_busy()

        threading.Thread(target=worker, daemon=True).start()
        return ""

    @Slot(result="QVariant")
    def mapPoints(self) -> list[dict]:
        """GPS 散点数据：按坐标聚合，返回 {lat, lon, count} 列表（无瓦片离线散点图）。"""
        rows = self.db.conn.execute(
            "SELECT gps_lat, gps_lon, COUNT(*) FROM photos"
            " WHERE status != 'missing' AND gps_lat IS NOT NULL AND gps_lon IS NOT NULL"
            " GROUP BY ROUND(gps_lat, 3), ROUND(gps_lon, 3)"
        ).fetchall()
        return [{"lat": r[0], "lon": r[1], "count": r[2]} for r in rows]

    @Slot(float, float, int, int, result="QVariant")
    def mapPhotos(self, lat: float, lon: float, offset: int = 0,
                  limit: int = 500) -> list[dict]:
        """按精确坐标取照片（散点点击 → 图库）。"""
        where = "ROUND(gps_lat,3)=? AND ROUND(gps_lon,3)=?"
        return self._pack(self._photo_rows(where, (round(lat, 3), round(lon, 3)),
                                           limit, offset))

    @Slot(result=int)
    def mapCount(self) -> int:
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing'"
            " AND gps_lat IS NOT NULL AND gps_lon IS NOT NULL"
        ).fetchone()[0]

    @Slot(float, float, result=str)
    def reverseGeocode(self, lat: float, lon: float) -> str:
        """逆地理编码：坐标 → 地名层级字符串（离线，需 models/geo/geo.sqlite）。
        数据缺失时返回空字符串，不崩。"""
        from photo_manager.core.geocode import get_coder
        try:
            return get_coder().reverse_geocode(lat, lon) or ""
        except Exception as e:  # pragma: no cover - 数据异常兜底
            log.warning("reverseGeocode 失败：%s", e)
            return ""

    # ---------- 照片堆叠（Stacks） ----------
    @Slot(result=str)
    def detectStacks(self) -> str:
        """重建照片堆叠（连拍/双格式），不删不改原图。返回统计文案。"""
        from photo_manager.core import stacks as stacks_mod
        try:
            stats = stacks_mod.detect_stacks(self.db)
            self._finish(_tr("照片堆叠完成：{p1} 个栈，").format(p1=stats['stacks'])
+                          _tr("包含 {p1} 张照片").format(p1=stats['photos']))
            if stats.get("stacks", 0) > 0:
                # 0.5.32：检测出栈后通知 QML 自动切到堆叠视图（Toast 由 _finish 已发一条，
                # QML 侧会再发一条切换提示覆盖）
                self.stacksDetected.emit(int(stats["stacks"]))
            return f"stacks={stats['stacks']} photos={stats['photos']}"
        except Exception as e:
            log.error("detectStacks 失败：%s", e)
            self._finish(_tr("照片堆叠失败：{p1}").format(p1=e))
            return "error"

    @Slot(int, int, result="QVariant")
    def galleryStacks(self, offset: int = 0, limit: int = 500) -> list[dict]:
        """堆叠视图：每栈返回代表帧一行 + stackId/stackCount。"""
        from photo_manager.core import stacks as stacks_mod
        rows = stacks_mod.stack_representatives(self.db, limit, offset)
        out = self._pack(rows)
        for i, d in enumerate(out):
            sid = rows[i][0]  # representative id == stacks.representative_photo_id
            cnt = self.db.conn.execute(
                "SELECT COUNT(*) FROM photos WHERE stack_id = "
                "(SELECT id FROM stacks WHERE representative_photo_id=?)",
                (sid,)).fetchone()[0]
            d["stackId"] = self.db.conn.execute(
                "SELECT id FROM stacks WHERE representative_photo_id=?", (sid,)
            ).fetchone()[0]
            d["stackCount"] = cnt
        return out

    @Slot(int, result="QVariant")
    def stackMembers(self, stack_id: int) -> list[dict]:
        """某栈的全部成员（用于展开浏览）。"""
        from photo_manager.core import stacks as stacks_mod
        rows = stacks_mod.stack_members(self.db, stack_id)
        out = self._pack(rows)
        for d in out:
            d["selected"] = False
        return out

    @Slot(result=int)
    def stackCount(self) -> int:
        from photo_manager.core import stacks as stacks_mod
        return stacks_mod.stack_count(self.db)

    # ---------- 虚拟相册（只存引用分组，不动照片文件） ----------
    @Slot(result="QVariant")
    def albums(self) -> list[dict]:
        """相册列表：id/name/photoCount/cover（封面缩略图 URL）。"""
        from photo_manager.core import albums as albums_mod

        out = albums_mod.list_albums(self.db)
        for d in out:
            d["cover"] = self._thumb_url(d.get("cover"))
        return out

    @Slot(str, result=int)
    def albumCreate(self, name: str) -> int:
        from photo_manager.core import albums as albums_mod

        aid = albums_mod.create_album(self.db, name)
        if aid:
            self._finish(_tr("已创建相册「{p1}」").format(p1=name.strip()))
        return aid

    @Slot(int, str, result=bool)
    def albumRename(self, album_id: int, name: str) -> bool:
        from photo_manager.core import albums as albums_mod

        return albums_mod.rename_album(self.db, album_id, name)

    @Slot(int, result=bool)
    def albumDelete(self, album_id: int) -> bool:
        """删除相册：只删分组与关联，绝不删除任何照片文件。"""
        from photo_manager.core import albums as albums_mod

        ok = albums_mod.delete_album(self.db, album_id)
        if ok:
            self._finish("相册已删除（照片文件不受影响）")
        return ok

    @Slot(int, "QVariant", result=int)
    def albumAddPhotos(self, album_id: int, ids) -> int:
        from PySide6.QtQml import QJSValue

        from photo_manager.core import albums as albums_mod

        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        n = albums_mod.add_photos(self.db, album_id, ids)
        if n > 0:
            self._finish(_tr("已把 {p1} 张照片加入相册").format(p1=n))
        return n

    @Slot(int, "QVariant", result=int)
    def albumRemovePhotos(self, album_id: int, ids) -> int:
        from PySide6.QtQml import QJSValue

        from photo_manager.core import albums as albums_mod

        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        return albums_mod.remove_photos(self.db, album_id, ids)

    @Slot(int, int, int, result="QVariant")
    def albumPhotos(self, album_id: int, offset: int = 0, limit: int = 500) -> list[dict]:
        from photo_manager.core import albums as albums_mod

        return self._pack(albums_mod.album_photos(self.db, album_id, limit, offset))

    @Slot(int, result=int)
    def albumPhotoCount(self, album_id: int) -> int:
        from photo_manager.core import albums as albums_mod

        return albums_mod.album_count(self.db, album_id)

    # ---------- 以图搜图（相似照片，CLIP 向量余弦） ----------
    @Slot(int, result=str)
    def findSimilar(self, photo_id: int) -> str:
        """以图搜图（后台）：按 CLIP 图像向量找最相似的照片。

        纯只读（不写库、不动原图）；完成后 emit similarFinished(JSON)。
        """
        from photo_manager.core.clip import find_similar as _find_similar

        with self._busy_lock:
            if self._busy > 0:
                self._finish("查找相似已取消：有任务正在运行，请稍候")
                return ""
            self._busy = 1
        self.message.emit(_tr("正在查找相似照片…"))
        def worker():
            try:
                res = _find_similar(self.db, int(photo_id))
                self._similar = res
                n = len(res)
                if n:
                    self._finish(_tr("相似照片查找完成：找到 {p1} 张").format(p1=n))
                else:
                    self._finish("没有找到相似照片（可能尚未生成语义向量）")
                self.similarFinished.emit(json.dumps({"count": n}))
            except Exception as e:
                log.exception("findSimilar 失败")
                self._finish(_tr("查找相似失败：{p1}").format(p1=e))
            finally:
                self._release_busy()

        threading.Thread(target=worker, daemon=True).start()
        return ""

    @Slot(result=int)
    def similarCount(self) -> int:
        return len(self._similar)

    @Slot(int, int, result="QVariant")
    def similarPhotos(self, offset: int = 0, limit: int = 500) -> list[dict]:
        """最近一次以图搜图的结果分页（保持相似度降序，附 score 字段）。"""
        res = self._similar or []
        part = res[offset:offset + limit]
        if not part:
            return []
        ids = [pid for pid, _ in part]
        q = ",".join("?" for _ in ids)
        rows = self.db.conn.execute(
            " SELECT id, thumbnail_path, file_name, taken_at, face_count, has_text,"
            " camera_model, file_path, width, height, rating, flag, color_label FROM photos"
            f" WHERE id IN ({q})", tuple(ids),
        ).fetchall()
        out = self._pack(rows)
        by_id = {d["id"]: d for d in out}
        scores = dict(res)
        ordered = []
        for pid in ids:
            d = by_id.get(pid)
            if d:
                d["score"] = scores.get(pid, 0)
                ordered.append(d)
        return ordered

    # ---------- 上传人脸搜图（0.5.37-1，YuNet 检测 + SFace 向量比对） ----------
    @Slot(str, result=str)
    def searchByFace(self, image_path: str) -> str:
        """上传人脸搜图（后台）：选择本地图片 → 检测人脸 → 与库内人脸向量比对。

        纯只读（不写库、不动原图）；完成后 emit similarFinished(JSON, kind=face)。
        """
        from photo_manager.core.faces import search_by_face

        with self._busy_lock:
            if self._busy > 0:
                self._finish("人脸搜索已取消：有任务正在运行，请稍候")
                return ""
            self._busy = 1
        self.message.emit(_tr("正在按人脸搜索照片…"))
        def worker():
            try:
                res = search_by_face(self.db, image_path, models_dir())
                self._face_search = res
                n = len(res)
                if n:
                    self._finish(_tr("人脸搜索完成：找到 {p1} 张相似照片").format(p1=n))
                else:
                    self._finish("没有找到相似的人脸（可先在工具中心运行人脸识别）")
                self.similarFinished.emit(json.dumps({"count": n, "kind": "face"}))
            except Exception as e:
                log.exception("searchByFace 失败")
                self._finish(_tr("人脸搜索失败：{p1}").format(p1=e))
            finally:
                self._release_busy()

        threading.Thread(target=worker, daemon=True).start()
        return ""

    @Slot(result=int)
    def faceSearchCount(self) -> int:
        return len(self._face_search)

    @Slot(int, int, result="QVariant")
    def faceSearchPhotos(self, offset: int = 0, limit: int = 500) -> list[dict]:
        """最近一次上传人脸搜图的结果分页（相似度降序，附 score 字段）。"""
        return self._paged_scored(self._face_search, offset, limit)

    def _paged_scored(self, res: list[tuple[int, float]], offset: int,
                      limit: int) -> list[dict]:
        part = (res or [])[offset:offset + limit]
        if not part:
            return []
        ids = [pid for pid, _ in part]
        q = ",".join("?" for _ in ids)
        rows = self.db.conn.execute(
            " SELECT id, thumbnail_path, file_name, taken_at, face_count, has_text,"
            " camera_model, file_path, width, height, rating, flag, color_label FROM photos"
            f" WHERE id IN ({q})", tuple(ids),
        ).fetchall()
        out = self._pack(rows)
        by_id = {d["id"]: d for d in out}
        scores = dict(res)
        ordered = []
        for pid in ids:
            d = by_id.get(pid)
            if d:
                d["score"] = scores.get(pid, 0)
                ordered.append(d)
        return ordered

    # ---------- 人脸模糊指数与清理（0.5.37-2） ----------
    @Slot(result=str)
    def faceBlurStatus(self) -> str:
        """模糊评分进度概况（JSON）：total/scored/missing(文件缺失)/unscored。"""
        conn = self.db.conn
        total = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
        scored = conn.execute(
            "SELECT COUNT(*) FROM faces WHERE blur IS NOT NULL").fetchone()[0]
        missing = conn.execute(
            "SELECT COUNT(*) FROM faces WHERE blur=-1").fetchone()[0]
        return json.dumps({"total": total, "scored": scored,
                           "missing": missing, "unscored": total - scored})

    @Slot(bool)
    def faceBlurBackfill(self, force: bool = False) -> None:
        """后台为人脸评分模糊指数（只写 faces.blur，不动其他数据）。

        force=False 只补未评分的；force=True 全量重评（0.5.42 算法升级，
        刷新旧分数用）。
        """
        from photo_manager.core.faces import backfill_face_blur

        def work():
            return backfill_face_blur(self.db, force=force)

        self._spawn("faceblur", "人脸模糊评分", work)

    @Slot("double", result="QVariant")
    def blurryFaces(self, threshold: float) -> list[dict]:
        """模糊指数 ≥ threshold 的人脸（降序），供清理弹窗展示与批量处理。

        每项含 faceId/photoId/name/personId/personName/blurIdx/thumb+clip（头像同款
        归一化映射）；已隐藏的不重复列出。
        """
        conn = self.db.conn
        rows = conn.execute(
            "SELECT f.id, f.photo_id, f.blur, f.person_id, f.bbox,"
            " p.file_name, p.thumbnail_path, p.width, p.height,"
            " p.thumb_width, p.thumb_height, p.file_path"
            " FROM faces f JOIN photos p ON p.id = f.photo_id"
            " WHERE f.blur IS NOT NULL AND f.blur >= ? AND f.hidden = 0"
            " ORDER BY f.blur DESC, f.id LIMIT 2000", (threshold,),
        ).fetchall()
        names = self._person_display_map()
        out = []
        for (fid, pid, blur, person_id, bbox, pname, tpath, w, h,
             tw, th, fpath) in rows:
            item = {
                "faceId": fid, "photoId": pid,
                "blurIdx": int(blur) if blur is not None else -1,
                "name": pname,
                "personId": person_id if person_id else 0,
                "personName": names.get(person_id, "") if person_id else "",
            }
            av = self._face_avatar((bbox, fpath, tpath, w, h, tw, th))
            if av:
                item.update(av)
            out.append(item)
        return out

    @Slot(int, bool, result=bool)
    def setFaceHidden(self, face_id: int, hidden: bool) -> bool:
        """隐藏/取消隐藏人脸标签：只在人物列表、人脸搜索、信息面板里不显示。

        照片、检测数据与人物归属全部保留，完全可逆。
        """
        conn = self.db.conn
        if not conn.execute("SELECT 1 FROM faces WHERE id=?", (face_id,)).fetchone():
            return False
        conn.execute("UPDATE faces SET hidden=? WHERE id=?",
                     (1 if hidden else 0, face_id))
        conn.commit()
        return True

    # ---------- 锁定只读（0.5.37-3，只改文件属性，不动任何数据） ----------
    @Slot("QVariant", bool, result=str)
    def lockReadOnlyIds(self, ids, lock: bool) -> str:
        """把所选照片的文件设为/解除只读。返回摘要文案。"""
        from photo_manager.core.system import set_files_readonly

        from PySide6.QtQml import QJSValue
        if isinstance(ids, QJSValue):
            ids = ids.toVariant()
        ids = [int(i) for i in (ids or [])]
        if not ids:
            return "未选择照片"
        q = ",".join("?" for _ in ids)
        rows = self.db.conn.execute(
            f"SELECT file_path FROM photos WHERE id IN ({q})", tuple(ids)
        ).fetchall()
        ok, skip = set_files_readonly([r[0] for r in rows], lock)
        return self._lock_summary(ok, skip, lock)

    @Slot(str, bool, result=str)
    def lockReadOnlyFolder(self, folder: str, lock: bool) -> str:
        """把某文件夹（含子文件夹）下所有在库照片设为/解除只读。"""
        from photo_manager.core.system import set_files_readonly

        rows = self.db.conn.execute(
            "SELECT file_path FROM photos WHERE status != 'missing'"
            " AND (folder_path = ? OR folder_path LIKE ? || '/%')",
            (folder, folder),
        ).fetchall()
        ok, skip = set_files_readonly([r[0] for r in rows], lock)
        return self._lock_summary(ok, skip, lock)

    @Slot(bool, result=str)
    def lockReadOnlyAll(self, lock: bool) -> str:
        """把全部在本软件管理范围内的照片设为/解除只读。"""
        from photo_manager.core.system import set_files_readonly

        rows = self.db.conn.execute(
            "SELECT file_path FROM photos WHERE status != 'missing'"
        ).fetchall()
        ok, skip = set_files_readonly([r[0] for r in rows], lock)
        return self._lock_summary(ok, skip, lock)

    @staticmethod
    def _lock_summary(ok: int, skip: int, lock: bool) -> str:
        verb = "锁定只读" if lock else "解除只读"
        msg = _tr("已{p1} {p2} 个文件").format(p1=verb, p2=ok)
        if skip:
            msg += _tr(" · 跳过 {p1} 个（缺失或被占用）").format(p1=skip)
        return msg

    # ---------- 导出历史（0.5.39「已导出」页） ----------
    @Slot(result=int)
    def exportHistoryCount(self) -> int:
        return self.db.conn.execute(
            "SELECT COUNT(*) FROM export_records").fetchone()[0]

    @Slot(int, int, result="QVariant")
    def exportHistory(self, offset: int = 0, limit: int = 500) -> list[dict]:
        """导出记录分页（时间倒序）。"""
        rows = self.db.conn.execute(
            "SELECT id, photo_id, file_name, dest_dir, fmt, res, exported_at"
            " FROM export_records ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        out = []
        for rid, pid, fname, dest, fmt, res, at in rows:
            res_txt = "原始" if res == "original" else _tr("短边{p1}").format(p1=res[1:])
            fmt_txt = "原格式" if fmt == "original" else fmt.upper()
            out.append({"id": rid, "photoId": pid or 0, "name": fname,
                        "destDir": dest, "fmt": fmt, "res": res,
                        "fmtText": fmt_txt, "resText": res_txt, "exportedAt": at})
        return out

    @Slot(result="QVariant")
    def statsDashboard(self) -> dict:
        """统计看板：总量 + 按年/月/设备/地点的分布。"""
        conn = self.db.conn
        totals = {
            "photos": conn.execute(
                "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0").fetchone()[0],
            "faces": conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0],
            "persons": conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0],
            "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "tags": conn.execute(
                "SELECT COUNT(DISTINCT tag) FROM photo_tags").fetchone()[0],
            "dupGroups": conn.execute(
                "SELECT COUNT(*) FROM (SELECT perceptual_hash FROM photos WHERE"
                " perceptual_hash IS NOT NULL AND perceptual_hash != ''"
                " AND status != 'missing' AND archived = 0 GROUP BY perceptual_hash HAVING COUNT(*)>1)"
            ).fetchone()[0],
            "movedOut": conn.execute(
                "SELECT COUNT(*) FROM move_out_records").fetchone()[0],
            "rated": conn.execute(
                "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0 AND rating > 0"
            ).fetchone()[0],
            "picked": conn.execute(
                "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0 AND flag='pick'"
            ).fetchone()[0],
            "rejected": conn.execute(
                "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0 AND flag='reject'"
            ).fetchone()[0],
        }

        def dist(sql: str) -> list[dict]:
            rows = conn.execute(sql).fetchall()
            return [{"key": r[0] or "-", "count": r[1]} for r in rows]

        return {
            "totals": totals,
            "byYear": dist("SELECT substr(COALESCE(sort_key,''),1,4), COUNT(*)"
                           " FROM photos WHERE status != 'missing' AND archived = 0"
                           " AND taken_at IS NOT NULL AND taken_at != ''"
                           " GROUP BY 1 ORDER BY 1 DESC"),
            "byMonth": dist("SELECT substr(COALESCE(sort_key,''),1,7), COUNT(*)"
                            " FROM photos WHERE status != 'missing' AND archived = 0"
                            " AND taken_at IS NOT NULL AND taken_at != ''"
                            " GROUP BY 1 ORDER BY 1 DESC"),
            "byDevice": dist("SELECT COALESCE(NULLIF(camera_model,''),'未知设备'),"
                             " COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0"
                             " GROUP BY camera_model ORDER BY 2 DESC"),
"byLocation": dist("SELECT ROUND(gps_lat,2)||','||ROUND(gps_lon,2),"
                           " COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0"
                           " AND gps_lat IS NOT NULL AND gps_lon IS NOT NULL"
                           " GROUP BY 1 ORDER BY 2 DESC"),
            "byRating": dist("SELECT CAST(rating AS TEXT), COUNT(*) FROM photos"
                             " WHERE status != 'missing' AND archived = 0 AND rating > 0"
                             " GROUP BY rating ORDER BY rating DESC"),
        }

    @Slot(result="QVariant")
    def dbDetail(self) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT LOWER(status), COUNT(*) FROM photos GROUP BY status"
        ).fetchall()
        status = {r[0]: r[1] for r in rows}
        roots = self.db.conn.execute(
            "SELECT path, last_scan_at FROM scan_roots ORDER BY last_scan_at DESC"
        ).fetchall()
        return {
            "photos": self.db.conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0],
            "indexed": status.get("indexed", 0),
            "failed": status.get("failed", 0),
            "missing": status.get("missing", 0),
            "faces": self.db.conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0],
            "persons": self.db.conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0],
            "events": self.db.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "tags": self.db.conn.execute("SELECT COUNT(*) FROM photo_tags").fetchone()[0],
            "roots": [{"path": r[0], "last": r[1] or ""} for r in roots],
        }

    @Slot(result="QVariant")
    def folderTreeAll(self) -> list[dict]:
        """管理路径的完整树（从 folder_path 构建，扁平列表含 depth/展开标记）。

        与 managedPaths 不同：按真实目录层级展开全部子文件夹，供树状图展示。
        """
        conn = self.db.conn
        rows = conn.execute(
            "SELECT DISTINCT folder_path FROM photos"
            " WHERE folder_path IS NOT NULL AND folder_path != ''"
        ).fetchall()
        paths = sorted({r[0].replace("\\", "/").rstrip("/") for r in rows})
        tree: dict = {}
        for p in paths:
            parts = p.split("/")
            node = tree
            for part in parts:
                node = node.setdefault(part, {})
        out: list[dict] = []
        expanded = self._tree_expanded

        def walk(node: dict, path: str, depth: int) -> None:
            items = sorted(node.items(), key=lambda kv: kv[0].lower())
            for name, sub in items:
                cur = path + "/" + name if path else name
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM photos WHERE folder_path = ? OR"
                    " folder_path LIKE ? ESCAPE '\\'",
                    (cur, cur + "/%"),
                ).fetchone()[0]
                has_child = bool(sub)
                out.append({
                    "name": name, "path": cur, "depth": depth,
                    "photoCount": cnt, "hasChildren": has_child,
                    "expanded": bool(sub and cur in expanded),
                })
                if sub and cur in expanded:
                    walk(sub, cur, depth + 1)

        walk(tree, "", 0)
        return out

    @Slot(str, bool)
    def folderToggle(self, path: str, expanded: bool) -> None:
        """记忆文件夹展开状态（树状图展开/收起）。"""
        if expanded:
            self._tree_expanded.add(path)
        else:
            self._tree_expanded.discard(path)

    @Slot(result="QVariant")
    def managedPaths(self) -> list[dict]:
        """当前管理的照片根路径：子路径并入其顶层父路径，附照片数，便于归集提醒。"""
        import os as _os

        from photo_manager.core.search import _like_escape

        conn = self.db.conn
        roots = [
            r[0] for r in conn.execute("SELECT path FROM scan_roots").fetchall()
        ]
        if not roots:
            roots = [
                r[0] for r in conn.execute(
                    "SELECT DISTINCT folder_path FROM photos"
                    " WHERE folder_path IS NOT NULL AND folder_path != ''"
                ).fetchall()
            ]
        cleaned: list[str] = []
        for p in roots:
            norm = p.rstrip("/")
            if not norm:
                continue
            if any(norm != q and norm.startswith(q.rstrip("/") + "/") for q in roots):
                continue
            if norm not in cleaned:
                cleaned.append(norm)
        out = []
        for norm in sorted(cleaned, key=str.lower):
            esc = _like_escape(norm)
            cnt = conn.execute(
                "SELECT COUNT(*) FROM photos WHERE folder_path = ? OR"
                " folder_path LIKE ? ESCAPE '\\'",
                (norm, norm + "/%"),
            ).fetchone()[0]
            last = conn.execute(
                "SELECT last_scan_at FROM scan_roots WHERE path=?", (norm,)
            ).fetchone()
            out.append({
                "path": _os.path.normpath(norm),
                "lastScan": (last[0] or "") if last else "",
                "photoCount": cnt,
            })
        return out

    def close(self) -> None:
        self.db.close()
