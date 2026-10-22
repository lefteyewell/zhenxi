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
"""搜索：FTS5 全文 + 结构化高级条件（AND/OR/NOT、时间/相机/标签/人物/GPS/人脸数）。

语法：
  普通词        FTS 匹配（文件名/文件夹/相机/镜头 + OCR trigram）
  tag:a,b      标签（逗号=OR）
  person:名     人物名（persons.name）
  camera:Canon  相机厂商/型号包含
  folder:dir    目录包含
  ext:raw       扩展名（raw/jpg/...）
  date:2025-03-02   拍摄日期（年月日或年月前缀）
  dates:2025-01-01..2025-06-30   日期范围
gps:39.9,116.3,5   距 (lat,lon) 5 公里内
   gps:北京 / gps:西湖   按地名搜索（逆地理编码解析为区域，需 models/geo/geo.sqlite）
   faces:2 / faces:0 / faces:>2   人脸数量
   rating:>=3 / rating:5 / rating:0   评级（1-5 星，0=未评级）
   flag:pick / flag:reject / flag:none   精选/排除旗标
   flag:archive / archived:yes   仅看已归档（隐藏出主时间轴的照片）
   archived:no    仅看未归档（默认；可不写）
   clip:查询       中文语义搜索（以文搜图，需 Chinese-CLIP 向量；模型缺失/无向量时返回空）
   color:red/红    按色标筛选（red/yellow/green/blue/purple，支持中文单字；color:none=未打色标）
   -词            排除（NOT）
  a OR b         同一子句内 OR
  "词"           精确匹配（不做近义扩展、不做前缀匹配）
  纯文本词/tag:值 默认做近义扩展（如 晚霞→日落/黄昏/夕阳，0.5.27）
"""
from __future__ import annotations

import datetime
import re

from photo_manager.core.db import Database

PREFIX_COLUMNS = ("file_name", "folder_path", "camera_make", "camera_model", "lens_model")

RESULT_COLS = (
    "id", "file_path", "file_name", "folder_path", "taken_at",
    "thumbnail_path", "face_count", "has_text", "camera_model",
    "width", "height", "rating", "flag", "color_label",
)

# 色标合法值（存储用英文键，UI 显示中文颜色名）
COLOR_LABELS = ("red", "yellow", "green", "blue", "purple")
_COLOR_ALIAS = {"红": "red", "黄": "yellow", "绿": "green",
                "蓝": "blue", "紫": "purple"}

_SAFE = re.compile(r"^[A-Za-z0-9_+]+$")
_FIELD = re.compile(r"^([a-zA-Z]+):(.*)$")
_FACES = re.compile(r"^(>=|<=|>|<|==)?\s*(\d+)$")

_KW = {"tag", "person", "camera", "folder", "ext", "type", "date", "dates", "gps", "faces", "text", "rating", "flag", "clip", "archived", "color"}
_EQUIV = {"type": "ext"}


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False

_RATING = re.compile(r"^(>=|<=|>|<|==)?\s*(\d+)$")

_FTS_SPECIAL = re.compile(r"[^A-Za-z0-9_+ ]")


def _prefix_term(tok: str, prefix: bool) -> str:
    """unicode61 前缀匹配词：ASCII 安全字符裸词（走分词前缀），否则引号包裹（精确词）。"""
    if _SAFE.match(tok):
        return tok + ("*" if prefix else "")
    return f'"{tok.replace(chr(34), chr(34) * 2)}"'


def _tokenize(q: str) -> list[str]:
    """按空白分词，但双引号内的空格不分割。

    支持 person:"人物 1" 这类带空格的值（自动命名的人物含空格，
    若直接按空格切分会被拆成 person:人物 与 1 两个条件，结果不精确）。
    引号**保留**在 token 上，供 _cond_for 判断该值需精确匹配（LIKE %x% 会把
    "人物 2" 与 "人物 20/200" 一并命中，必须用 = 才是精确语义）。
    """
    out: list[str] = []
    cur: list[str] = []
    quoted = False
    in_quote = False
    for ch in q:
        if ch == '"' or ch in "“”":
            in_quote = not in_quote
            quoted = True
            # 引号本身写入 token，作为"需精确匹配"的标记
            cur.append('"')
            continue
        if not in_quote and ch.isspace():
            if cur:
                out.append("".join(cur))
                cur = []
            continue
        cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# 繁简归一化（0.5.59）：自实现字符级变体表（替代 zhconv——GPLv2+ 是开源
# 分发障碍；zhvar 基于 Unicode Unihan 数据 + 人工补充，一简对多繁全展开，
# 搜索 OR 匹配召回更高。见 core/zhvar.py 与 tools/gen_zhvar.py）
from photo_manager.core.zhvar import variants as _variants


def _or_like(col: str, values: str) -> tuple[str, list]:
    parts = [v.strip() for v in values.split(",") if v.strip()]
    if not parts:
        return "", []
    vs: list[str] = []
    for p in parts:
        vs.extend(_variants(p))
    cond = "(" + " OR ".join(f"{col} LIKE ? ESCAPE '\\'" for _ in vs) + ")"
    return cond, [f"%{_like_escape(v)}%" for v in vs]


# ---- 近义扩展（0.5.27）----
# 设计分工：词表（打标）保持一词一义的精瘦状态，歧义留给查询端消化——
# 搜索时把查询词展开为组内近义词一并 OR 匹配，词库无需为同义词冗余打标。
# 仅作用于：纯文本查询、tag: 值。不作用于：
#   - 引号包裹的值（"日落" = 精确匹配，不扩展）
#   - -排除词（排除语义尊重用户显式意图，不扩大否定范围）
#   - text:/folder:/ext:/camera:/person: 等结构化字段（OCR/路径/属性按字面匹配）
SYNONYM_GROUPS: dict[str, tuple[str, ...]] = {
    "日落": ("晚霞", "黄昏", "夕阳"),
    "日出": ("朝阳", "晨曦", "曙光"),
    "大海": ("海洋", "海边", "海滨", "海岸"),
    "雪山": ("雪峰", "雪景", "冰川"),
    "森林": ("树林", "林间", "林地"),
    "草原": ("草地", "草坪", "牧场"),
    "花卉": ("鲜花", "花朵", "花海"),
    "儿童": ("孩子", "小孩", "宝宝", "小朋友"),
    "宠物": ("萌宠", "爱宠", "喵星人", "汪星人"),
    "美食": ("食物", "菜品", "美味", "佳肴"),
    "聚会": ("派对", "联欢", "团建"),
    "会议": ("例会", "座谈会", "会务"),
    "婚礼": ("婚宴", "结婚"),
    "夜景": ("夜色", "夜晚", "夜幕"),
    "毕业": ("毕业典礼", "学位服"),
}
# 单个查询词最多展开成几个匹配词（含原词），防 LIKE/FTS 条件爆炸
SYN_MAX_TERMS = 5

# 双向索引：组内任一词都能展开出整组（保序去重）
_SYNONYM_INDEX: dict[str, tuple[str, ...]] = {}
for _k, _vs in SYNONYM_GROUPS.items():
    for _w in (_k,) + _vs:
        _SYNONYM_INDEX.setdefault(_w, tuple(dict.fromkeys((_k,) + _vs)))
del _k, _vs, _w


def _expand_synonyms(term: str) -> list[str]:
    """近义词展开（原词在最前，保序去重，限 SYN_MAX_TERMS）；无组的词原样返回。"""
    group = _SYNONYM_INDEX.get(term)
    if not group:
        return [term]
    return [term] + [w for w in group if w != term][: SYN_MAX_TERMS - 1]


def _unquote(body: str) -> tuple[str, bool]:
    """剥离引号包裹；返回 (内容, 是否精确匹配)。引号可能来自 _tokenize 的保留标记。"""
    if len(body) >= 2 and body.startswith('"') and body.endswith('"'):
        return body[1:-1].strip(), True
    return body, False


def _faces_cond(tok: str, negate: bool) -> tuple[str, list] | None:
    m = _FACES.match(tok)
    if not m:
        return None
    op, num = m.group(1) or "=", int(m.group(2))
    cond = f"face_count {op} ?" if op != "=" else "face_count = ?"
    if negate:
        cond = "(NOT " + cond + ")"
    return cond, [num]


def _cond_for(tok: str, prefix: bool, db=None) -> tuple[str, list]:
    """单个 token → (SQL 条件, 参数)；未知字段名按普通词处理。"""
    negate = tok.startswith("-") and len(tok) > 1
    body = tok[1:] if negate else tok
    # 剥引号：引号包裹 = 精确匹配（不做近义扩展、不做前缀匹配）
    body, exact = _unquote(body)
    if not body:
        return "", []

    m = _FIELD.match(body)
    if m and m.group(1).lower() in _KW:
        kw = _EQUIV.get(m.group(1).lower(), m.group(1).lower())
        val = m.group(2)
        if kw == "tag":
            parts = [v.strip() for v in val.split(",") if v.strip()]
            if not parts:
                return "", []
            # 层级标签（路径式，/ 分隔）：对任意节点名 X，
            # 既精确匹配 X，也匹配其子孙 X/...（前缀），并兼容旧式模糊包含（%X%）。
            conds = []
            params = []
            for p in parts:
                pval, pexact = _unquote(p)
                if not pval:
                    continue
                # 近义扩展（0.5.27）：引号精确值与排除条件不扩展
                terms = [pval] if (pexact or negate) else _expand_synonyms(pval)
                for t in terms:
                    # 繁简变体：任一字形都能命中（0.5.25）
                    for v in _variants(t):
                        esc = "%" + _like_escape(v) + "%"
                        # 命名为 prefix_pat：不可用形参名 prefix（bool），否则遮蔽入参
                        prefix_pat = _like_escape(v) + "/%"
                        conds.append(
                            "EXISTS (SELECT 1 FROM photo_tags t WHERE t.photo_id = photos.id"
                            " AND (t.tag = ? OR t.tag LIKE ? ESCAPE '\\'"
                            " OR t.tag LIKE ? ESCAPE '\\'))"
                        )
                        params.extend([v, prefix_pat, esc])
            sql = "(" + " OR ".join(conds) + ")"
            if negate:
                sql = "(NOT " + sql + ")"
            return sql, params
        if kw == "person":
            parts = [v.strip() for v in val.split(",") if v.strip()]
            if not parts:
                return "", []
            # 未命名人物在库中 name 为 NULL，界面显示为 "人物 N"（见 LibraryBridge.people
            # 的 COALESCE(name,'人物 '||id)）。此处必须用同样的 COALESCE，否则
            # person:人物 永远匹配不到任何未命名人物（NULL LIKE 恒为假）。
            # 引号包裹的值精确匹配（=），否则模糊（LIKE）：
            # LIKE '%人物 2%' 会把 "人物 20/200" 一起命中，语义错误。
            name_expr = "COALESCE(pe.name, '人物 ' || pe.id)"
            conds: list[str] = []
            params: list = []
            for p in parts:
                if len(p) >= 2 and p.startswith('"') and p.endswith('"'):
                    pv = p[1:-1].strip()
                    if not pv:
                        continue
                    conds.append(
                        "EXISTS (SELECT 1 FROM faces f JOIN persons pe ON pe.id = f.person_id"
                        f" WHERE f.photo_id = photos.id AND {name_expr} = ?)")
                    params.append(pv)
                else:
                    conds.append(
                        "EXISTS (SELECT 1 FROM faces f JOIN persons pe ON pe.id = f.person_id"
                        f" WHERE f.photo_id = photos.id AND {name_expr} LIKE ? ESCAPE '\\')")
                    params.append(f"%{_like_escape(p)}%")
            if not conds:
                return "", []
            sql = "(" + " OR ".join(conds) + ")"
            if negate:
                sql = "(NOT " + sql + ")"
            return sql, params
        if kw == "camera":
            if "," in val:
                return _camera_multi(val, negate)
            # COALESCE 处理 NULL：camera_make/model/lens 均可空（无 EXIF 相机信息）。
            # 否则 NOT(a LIKE ? OR b LIKE ? ...) 在 NULL 列上三值逻辑为 NULL，
            # -camera:x 会把「无相机信息的照片」也错误排除（排除搜索恒为空）。
            base = ("(COALESCE(camera_make,'') LIKE ? ESCAPE '\\'"
                    " OR COALESCE(camera_model,'') LIKE ? ESCAPE '\\'"
                    " OR COALESCE(lens_model,'') LIKE ? ESCAPE '\\'"
                    " OR file_name LIKE ? ESCAPE '\\')")
            if negate:
                base = "(NOT " + base + ")"
            return base, [f"%{_like_escape(val.strip())}%"] * 4
        if kw == "folder":
            cond, params = _or_like("folder_path", val)
            if negate:
                cond = "(NOT " + cond + ")"
            return cond, params
        if kw in ("ext", "type"):
            cond, params = _or_like("lower(ext)", val.lower())
            if negate:
                cond = "(NOT " + cond + ")"
            return cond, params
        if kw == "date":
            d = val.strip()
            cond = "sort_key LIKE ?"
            if negate:
                cond = "(NOT " + cond + ")"
            return cond, [d + "%"]
        if kw == "dates":
            a, _, b = val.partition("..")
            # sort_key 用 T 分隔（如 2025-06-30T10:00:00），上界必须同样用 T，
            # 用空格会比所有当日记录小（' ' < 'T'），导致末日整天被排除。
            cond = "(sort_key >= ? AND sort_key <= ?)"
            if negate:
                cond = "(NOT " + cond + ")"
            return cond, [a.strip(), b.strip() + "T23:59:59"]
        if kw == "text":
            v = val.strip()
            if v:
                # 繁简变体 OR：OCR 文本无论以何种字形入库都能命中（0.5.25）
                vars_ = _variants(v)
                likes = " OR ".join(f"ocr_text LIKE ? ESCAPE '\\'" for _ in vars_)
                cond = f"(has_text = 1 AND ({likes}))"
                if negate:
                    cond = "(NOT " + cond + ")"
                return cond, [f"%{_like_escape(x)}%" for x in vars_]
            cond = "(has_text = 1)"
            if negate:
                cond = "(NOT " + cond + ")"
            return cond, []
        if kw == "gps":
            raw = val.strip()
            parts = [p.strip() for p in raw.split(",")]
            # 地名搜索：非「lat,lon,rkm」三数值 → 经逆地理编码解析为 bbox
            if len(parts) != 3 or not all(_is_float(p) for p in parts):
                try:
                    from photo_manager.core.geocode import get_coder
                    bbox = get_coder().place_to_bbox(raw)
                except Exception:
                    bbox = None
                if not bbox:
                    return "", []
                minlat, maxlat, minlon, maxlon = bbox
                cond = (
                    "(gps_lat IS NOT NULL AND gps_lon IS NOT NULL"
                    f" AND gps_lat BETWEEN {minlat!r} AND {maxlat!r}"
                    f" AND gps_lon BETWEEN {minlon!r} AND {maxlon!r})"
                )
                if negate:
                    cond = "(NOT " + cond + ")"
                return cond, []
            lat, lon, rkm = float(parts[0]), float(parts[1]), float(parts[2])
            import math
            if not all(math.isfinite(v) for v in (lat, lon, rkm)) or rkm < 0:
                return "", []
            # 小半径球面近似（弧度制）：
            #   dy = Δlat·rad, dx = cos(lat)·Δlon·rad, dist² = (dx²+dy²) <= (rkm/6371)²
            rad = math.pi / 180.0
            lat_cos = math.cos(lat * rad)
            dy = f"((gps_lat - {lat!r}) * {rad!r})"
            dx = f"(({lat_cos!r}) * (gps_lon - {lon!r}) * {rad!r})"
            r_rad = rkm / 6371.0
            cond = (f"(gps_lat IS NOT NULL AND gps_lon IS NOT NULL"
                    f" AND ({dx}*{dx} + {dy}*{dy}) <= {r_rad!r}*{r_rad!r})")
            if negate:
                cond = "(NOT " + cond + ")"
            return cond, []
        if kw == "faces":
            fc = _faces_cond(val, negate)
            if fc:
                return fc
            return "", []
        if kw == "rating":
            m = _RATING.match(val)
            if not m:
                return "", []
            op, num = m.group(1) or "=", int(m.group(2))
            num = max(0, min(5, num))
            cond = f"rating {op} ?" if op != "=" else "rating = ?"
            if negate:
                cond = "(NOT " + cond + ")"
            return cond, [num]
        if kw == "flag":
            v = val.strip().lower()
            # none 分支的 SQL 不含占位符，必须返回空参数列表；
            # 此前无条件 return [v]，导致 sqlite3 报
            # "Incorrect number of bindings supplied"（flag:none 一搜就崩）。
            if v == "none":
                cond = "(flag = '' OR flag IS NULL)"
                if negate:
                    cond = "(NOT " + cond + ")"
                return cond, []
            if v == "archive":
                # flag:archive 是 archived=1 的友好别名（归档=隐藏出主时间轴）
                cond = "archived = 1"
                if negate:
                    cond = "(NOT " + cond + ")"
                return cond, []
            if v in ("pick", "reject"):
                cond = "flag = ?"
                if negate:
                    cond = "(NOT " + cond + ")"
                return cond, [v]
            return "", []
        if kw == "archived":
            v = val.strip().lower()
            on = v in ("1", "true", "yes", "y", "on")
            cond = "archived = 1" if on else "archived = 0"
            if negate:
                cond = "(NOT " + cond + ")"
            return cond, []
        if kw == "color":
            v = val.strip().lower()
            v = _COLOR_ALIAS.get(val.strip(), v)  # 中文单字别名（红→red 等）
            if v in ("none", "无", "未打"):
                cond = "(color_label IS NULL OR color_label = '')"
                if negate:
                    cond = "(NOT " + cond + ")"
                return cond, []
            if v in COLOR_LABELS:
                # COALESCE 处理 NULL：否则 NOT (color_label = 'x') 在
                # color_label 为 NULL 时三值逻辑结果仍为 NULL，未打色标的照片
                # 会被 -color:x 错误排除。
                cond = "COALESCE(color_label, '') = ?"
                if negate:
                    cond = "(NOT " + cond + ")"
                return cond, [v]
            return "", []
        if kw == "clip":
            v = val.strip()
            if not v:
                return "", []
            ids = _clip_search_ids(db, v) if db is not None else []
            if not ids:
                # 模型缺失或库中无语义向量 → 不匹配任何照片（语义搜索为空，不崩）
                return "0=1", []
            marks = ",".join("?" * len(ids))
            cond = f"(photos.id IN ({marks}))"
            if negate:
                cond = "(NOT " + cond + ")"
            return cond, list(ids)

    # ---- 普通词（或未知字段）----
    # 中文（非 ASCII）无法可靠用 unicode61 分词做前缀匹配，统一走 LIKE 子串。
    # 近义扩展（0.5.27）：引号精确值与排除条件不扩展；扩展词各自再做繁简变体。
    terms = [body] if (exact or negate) else _expand_synonyms(body)
    if len(body) >= 3 and _SAFE.match(body):
        # 繁简变体：photos_fts/ocr_fts/标签对每种字形各查一遍 OR（0.5.25）
        conds = []
        params: list = []
        for t in terms:
            for v in _variants(t):
                term = _prefix_term(v, prefix and not exact)
                pfts = " OR ".join(f"{col}:{term}" for col in PREFIX_COLUMNS)
                ofts = f'"{v.replace(chr(34), chr(34) * 2)}"'
                conds.append(
                    "(id IN (SELECT rowid FROM photos_fts WHERE photos_fts MATCH ?)"
                    " OR id IN (SELECT rowid FROM ocr_fts WHERE ocr_fts MATCH ?)"
                    " OR EXISTS (SELECT 1 FROM photo_tags t WHERE t.photo_id = photos.id"
                    " AND t.tag LIKE ? ESCAPE '\\'))"
                )
                params.extend([pfts, ofts, f"%{_like_escape(v)}%"])
        cond = "(" + " OR ".join(conds) + ")"
        if negate:
            cond = "(NOT " + cond + ")"
        return cond, params
    cond_parts = []
    params = []
    cols = ("file_name", "folder_path", "camera_model", "camera_make",
            "lens_model", "ocr_text")
    for t in terms:
        for v in _variants(t):
            pat = f"%{_like_escape(v)}%"
            for col in cols:
                cond_parts.append(f"{col} LIKE ? ESCAPE '\\'")
                params.append(pat)
            cond_parts.append(
                "EXISTS (SELECT 1 FROM photo_tags t WHERE t.photo_id = photos.id"
                " AND t.tag LIKE ? ESCAPE '\\')")
            params.append(pat)
    cond = "(" + " OR ".join(cond_parts) + ")"
    if negate:
        cond = "(NOT " + cond + ")"
    return cond, params


def _clip_search_ids(db, query: str, topk: int = 50,
                     rel_drop: float = 0.05, abs_floor: float = 0.20,
                     svc=None) -> list[int]:
    """中文语义检索：编码查询文本，与 photo_embeddings 中已存图像向量算余弦 top-k。

    模型缺失 / 库无向量时返回空列表（调用方据此返回"无结果"而非崩溃）。
    分块读取避免大库一次载入全部向量。

    结果过滤（0.5.24 修复"语义回退带出大量无关照片"）：
    - 相对阈值：只保留相似度 >= best-rel_drop 的照片。CLIP 文图余弦分布很挤
      （实测同库不同查询整体落在 0.29~0.43），绝对阈值滤不动，必须相对 best 收紧；
    - 数量上限 topk（语义检索是"最相似"而非"精确匹配"，不该把半个库都带出来）；
    - 绝对下限 abs_floor 兜底（与场景打标 CLIP_SIM_THRESHOLD 对齐）。
    :param svc: 可注入的 clip 服务（测试用）；None 则 get_service()。
    """
    import numpy as np

    from photo_manager.core.clip import MODEL_ID, ClipUnavailable, get_service

    try:
        svc = svc or get_service()
        if not svc.available:
            return []
        qv = svc.encode_text(query)
    except (ClipUnavailable, Exception):
        return []

    scored: list[tuple[float, int]] = []
    chunk, last = 5000, 0
    while True:
        rows = db.conn.execute(
            "SELECT photo_id, embedding FROM photo_embeddings "
            "WHERE model = ? AND photo_id > ? ORDER BY photo_id LIMIT ?",
            (MODEL_ID, last, chunk),
        ).fetchall()
        if not rows:
            break
        last = rows[-1][0]
        mat = np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
        sims = mat @ qv  # 向量已 L2 归一化，点积即余弦相似度
        scored.extend(zip(sims.tolist(), [r[0] for r in rows]))
    if not scored:
        return []
    scored.sort(key=lambda x: -x[0])
    cutoff = max(abs_floor, scored[0][0] - rel_drop)
    return [pid for s, pid in scored[:topk] if s >= cutoff][:topk]


def _camera_multi(val: str, negate: bool) -> tuple[str, list]:
    """camera:a,b → 每个值匹配 4 列（a 或 b）。"""
    conds, params = [], []
    for v in val.split(","):
        if not v.strip():
            continue
        conds.append("(COALESCE(camera_make,'') LIKE ? ESCAPE '\\'"
                     " OR COALESCE(camera_model,'') LIKE ? ESCAPE '\\'"
                     " OR COALESCE(lens_model,'') LIKE ? ESCAPE '\\'"
                     " OR file_name LIKE ? ESCAPE '\\')")
        params += [f"%{_like_escape(v.strip())}%"] * 4
    if not conds:
        return "", []
    sql = "(" + " OR ".join(conds) + ")"
    if negate:
        sql = "(NOT " + sql + ")"
    return sql, params


class PhotoSearch:
    def __init__(self, db: Database):
        self.db = db

    def query(self, q: str, limit: int = 200, prefix: bool = True,
              offset: int = 0) -> list[dict]:
        tokens = [t for t in _tokenize(q) if t]
        if not tokens:
            return []

        # 解析：组间 AND；组内 OR（token 为 OR 时合并左右条件）
        groups: list[list[tuple[str, list]]] = []
        cur: list[tuple[str, list]] = []
        prev_was_or = False
        for tok in tokens:
            if tok.lower() == "or" and cur:
                prev_was_or = True
                continue
            cond, params = _cond_for(tok, prefix, self.db)
            if not cond:
                continue
            if prev_was_or and cur:
                cur.append((cond, params))
            else:
                if cur:
                    groups.append(cur)
                cur = [(cond, params)]
            prev_was_or = False
        if cur:
            groups.append(cur)

        conds, params = [], []
        for group in groups:
            if len(group) == 1:
                c, p = group[0]
                conds.append(c)
                params += p
            else:
                sub = "(" + " OR ".join(c for c, _ in group) + ")"
                conds.append(sub)
                params += [p for _, p in group for p in p]
        if not conds:
            return []
        where = " AND ".join(conds)
        # 默认隐藏已归档照片（归档=从主时间轴/搜索移出，仅归档视图或显式
        # archived:yes / flag:archive 才可见）。显式指定归档条件时不加默认排除。
        explicit_archived = any(
            t.lower().startswith("archived:") or t.lower() in ("flag:archive", "-flag:archive")
            for t in tokens
        )
        status_clause = "photos.status != 'missing'"
        if not explicit_archived:
            status_clause += " AND photos.archived = 0"
        cols = ", ".join(f"photos.{c}" for c in RESULT_COLS)
        rows = self.db.conn.execute(
            f"SELECT {cols} FROM photos WHERE {where} AND {status_clause}"
            " ORDER BY photos.sort_key DESC, photos.id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        if not rows and not any(":" in t for t in tokens):
            # 语义回退：纯文本且全文（文件名/OCR 等）零命中时，尝试以文搜图。
            # "室内"这类文件名与照片内文字都不含的词，只有走 CLIP 语义才有结果
            # （等价于 clip:室内；模型缺失或库中无向量时 _clip_search_ids 返回空，
            # 行为与之前一致）。显式带语法前缀的查询不回退，尊重用户意图。
            # 回退用比 clip: 更紧的窗口（topk20/±0.03）：回退结果对用户是"搜索结果"，
            # 宁少勿滥；探索性宽搜索请用 clip: 语法。
            ids = _clip_search_ids(self.db, q, topk=20, rel_drop=0.03)
            if ids:
                marks = ",".join("?" * len(ids))
                fetch = (
                    f"SELECT {cols} FROM photos WHERE photos.id IN ({marks})"
                    f" AND {status_clause}"
                )
                by_id = {
                    r[0]: dict(zip(RESULT_COLS, r))
                    for r in self.db.conn.execute(fetch, tuple(ids)).fetchall()
                }
                # 保持语义相似度降序
                rows = [
                    tuple(by_id[pid][c] for c in RESULT_COLS)
                    for pid in ids if pid in by_id
                ][:limit]
        return [dict(zip(RESULT_COLS, r)) for r in rows]

    def suggest(self, q: str, limit: int = 10) -> list[str]:
        """文件名/目录前缀联想（搜索框自动补全）。繁简变体均联想（0.5.25）。"""
        if not q:
            return []
        out: list[str] = []
        seen: set[str] = set()
        for vq in _variants(q):
            pat = vq.replace("%", r"\%").replace("_", r"\_") + "%"
            rows = self.db.conn.execute(
                "SELECT file_name FROM photos WHERE status != 'missing'"
                " AND file_name LIKE ? ESCAPE '\\'"
                " GROUP BY file_name LIMIT ?",
                (pat, limit),
            ).fetchall()
            for r in rows:
                if r[0] not in seen:
                    seen.add(r[0])
                    out.append(r[0])
            if len(out) >= limit:
                return out[:limit]
        for vq in _variants(q):
            if len(out) >= limit:
                break
            pat = f"%{_like_escape(vq)}%"
            dirs = self.db.conn.execute(
                "SELECT folder_path FROM photos WHERE status != 'missing'"
                " AND folder_path LIKE ? ESCAPE '\\'"
                " GROUP BY folder_path LIMIT ?",
                (pat, limit - len(out)),
            ).fetchall()
            for (d,) in dirs:
                if d and d not in seen:
                    seen.add(d)
                    out.append(d)
        return out[:limit]


def on_this_day(db: "Database", month_day: str = "", limit: int = 2000,
                offset: int = 0) -> list[dict]:
    """往年今日：拍摄于指定月-日（MM-DD，默认今天）的历史照片，按时间升序，排除今年。

    返回每条含 year 字段（int，用于前端按年分组）。不触碰原图、不删除数据。
    sort_key / taken_at 格式均为 YYYY-MM-DDTHH:MM:SS，故 substr(...,6,5)=MM-DD。
    """
    if not month_day:
        month_day = datetime.date.today().strftime("%m-%d")
    cur_year = datetime.date.today().strftime("%Y")
    rows = db.conn.execute(
        " SELECT id, thumbnail_path, file_name, taken_at, face_count, has_text,"
        " camera_model, file_path, width, height, rating, flag, color_label FROM photos"
        " WHERE status != 'missing'"
        " AND substr(COALESCE(sort_key, taken_at, ''),6,5) = ?"
        " AND substr(COALESCE(sort_key, taken_at, ''),1,4) != ?"
        " ORDER BY COALESCE(sort_key, taken_at, '') ASC, id ASC"
        " LIMIT ? OFFSET ?",
        (month_day, cur_year, limit, offset),
    ).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r[0],
            "thumb": r[1],
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
            "year": int((r[3] or "")[:4] or 0),
        })
    return out
