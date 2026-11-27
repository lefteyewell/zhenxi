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
"""离线逆地理编码（反向地理编码）。

数据来源：GeoNames cities1000（全球 ~13 万城市，CC BY 4.0，署名见 build_geo.py）。
完全离线、不联网；经纬度 → 最近邻地名层级字符串；地名 → bbox 用于搜索。

设计约束：
- 不依赖 scipy（环境未安装）；用 SQLite 包围盒预筛 + haversine 最近邻。
- 模型缺失/数据未构建时安全降级（返回 None / 空），不崩。
- 不修改任何外部数据，仅读取 models/geo/geo.sqlite。
"""

from __future__ import annotations

import logging
import math
import os
import threading

from photo_manager import models_dir

log = logging.getLogger(__name__)

_EARTH_R_KM = 6371.0088

# 显示层地名映射（0.7.8）：GeoNames 是国际数据集，个别国家/地区名与
# 中国官方表述不一致。只在**显示**时替换，绝不改 geo.sqlite 原始数据，
# 数据集升级也不会被覆盖。键为 GeoNames 原始名（含大小写变体）。
_DISPLAY_NAME_MAP = {
    "Taiwan": "中国台湾",
    "taiwan": "中国台湾",
    "TAIWAN": "中国台湾",
    "Taiwan, China": "中国台湾",
    "Republic of China": "中国台湾",
    "Hong Kong": "中国香港",
    "hong kong": "中国香港",
    "Hong Kong SAR": "中国香港",
    "Hong Kong SAR, China": "中国香港",
    "Macao": "中国澳门",
    "Macau": "中国澳门",
    "macao": "中国澳门",
    "Macao SAR": "中国澳门",
    "Macao SAR, China": "中国澳门",
}


def localized_name(name: str | None) -> str | None:
    """把 GeoNames 原始地名转为本地化显示名（未命中原样返回）。"""
    if not name:
        return name
    return _DISPLAY_NAME_MAP.get(name, name)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * _EARTH_R_KM * math.asin(min(1.0, math.sqrt(a)))


class GeoCoder:
    """轻量离线逆地理编码器（线程安全、懒加载）。"""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or os.path.join(models_dir(), "geo", "geo.sqlite")
        self._conn = None
        self._lock = threading.Lock()
        self._cache: dict[tuple, str | None] = {}
        self.available = os.path.exists(self._db_path)
        if not self.available:
            log.warning("地理数据库缺失：%s（运行 tools/build_geo.py 生成）",
                        self._db_path)

    # ---- 内部：懒连接 ----
    def _connect(self):
        if self._conn is None:
            if not self.available:
                return None
            try:
                import sqlite3
                self._conn = sqlite3.connect(self._db_path)
                self._conn.row_factory = sqlite3.Row
                # 创建经纬度索引（若尚未存在，仅加速，不写数据）
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_places_lat ON places(lat)"
                )
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_places_lon ON places(lon)"
                )
            except Exception as e:  # pragma: no cover - 数据损坏兜底
                log.error("地理数据库打开失败：%s", e)
                self._conn = None
        return self._conn

    def _q(self, sql: str, params=()):
        with self._lock:
            conn = self._connect()
            if conn is None:
                return []
            try:
                return conn.execute(sql, params).fetchall()
            except Exception as e:  # pragma: no cover
                log.error("地理查询失败：%s | %s", sql, e)
                return []

    # ---- 反地理编码：坐标 → 地名层级字符串 ----
    def reverse_geocode(self, lat: float, lon: float) -> str | None:
        if lat is None or lon is None:
            return None
        key = (round(lat, 3), round(lon, 3))
        if key in self._cache:
            return self._cache[key]
        result = self._reverse_core(lat, lon)
        self._cache[key] = result
        return result

    def _reverse_core(self, lat: float, lon: float) -> str | None:
        # 逐步扩大搜索半径，直到找到候选
        for deg in (1.0, 3.0, 8.0, 30.0):
            cands = self._q(
                "SELECT geoname_id, name, ascii_name, country, admin1, admin2, "
                "lat, lon "
                "FROM places WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
                (lat - deg, lat + deg, lon - deg, lon + deg),
            )
            if not cands:
                continue
            best = None
            best_d = 1e9
            for c in cands:
                d = _haversine_km(lat, lon, c["lat"], c["lon"])
                if d < best_d:
                    best_d = d
                    best = c
            if best is None:
                continue
            return self._format(best, best_d)

        # 全球范围内最近（兜底，极少触发）
        allc = self._q(
            "SELECT geoname_id, name, ascii_name, country, admin1, admin2, lat, lon "
            "FROM places"
        )
        best = None
        best_d = 1e9
        for c in allc:
            d = _haversine_km(lat, lon, c["lat"], c["lon"])
            if d < best_d:
                best_d = d
                best = c
        return self._format(best, best_d) if best else None

    def _format(self, c, dist_km: float) -> str:
        # 0.7.8b：只显示城市或比城市更小的地名（用户要求：不显示国家/地区层级）。
        # cities1000 数据本身即城市/城镇/村庄级，取其名（中文别名优先）即可；
        # admin1/国家层级一律不再输出，争议表述映射只在城市名命中时仍有意义。
        alias = self._alias_of(c["geoname_id"])
        name = localized_name(alias or c["ascii_name"] or c["name"] or "")
        s = name
        # 距离过远（>5km）时标注，提示仅为最近参考
        # （0.7.8d：50→5km。自动地名取"最近地理条目"，照片可能在名字所在
        # 位置数公里外拍摄——如城区内取到 1~2km 外的村镇条目，需要提示）
        if dist_km and dist_km > 5:
            s += f" · 约{dist_km:.0f}km"
        return s

    def _alias_of(self, geoname_id) -> str | None:
        if geoname_id is None:
            return None
        rows = self._q(
            "SELECT alias FROM aliases WHERE geoname_id=? AND kind IN ('city','landmark') "
            "ORDER BY length(alias) LIMIT 1",
            (geoname_id,),
        )
        return rows[0]["alias"] if rows else None

    def _country_name(self, code: str) -> str | None:
        rows = self._q("SELECT name FROM countries WHERE code=?", (code,))
        if rows:
            return rows[0]["name"]
        # 中文国家别名
        a = self._q(
            "SELECT alias FROM aliases WHERE country=? AND kind='country' LIMIT 1",
            (code,),
        )
        return a[0]["alias"] if a else code

    # ---- 正地理编码：地名 → bbox（用于 gps:地名 搜索） ----
    def place_to_bbox(self, name: str) -> tuple[float, float, float, float] | None:
        """返回 (minlat, maxlat, minlon, maxlon)，未匹配返回 None。"""
        q = (name or "").strip()
        if not q:
            return None
        like = f"%{q}%"
        pts: list[tuple[float, float]] = []

        # 1) 城市/景点别名（精确优先，再模糊）
        rows = self._q(
            "SELECT p.lat, p.lon FROM places p JOIN aliases a "
            "ON a.geoname_id=p.geoname_id AND a.kind IN ('city','landmark') "
            "WHERE a.alias = ? OR a.alias LIKE ?",
            (q, like),
        )
        pts += [(r["lat"], r["lon"]) for r in rows]

        # 2) 城市名直接匹配（含中文字段 name / ascii）
        rows = self._q(
            "SELECT lat, lon FROM places "
            "WHERE name = ? OR ascii_name = ? OR name LIKE ? OR ascii_name LIKE ?",
            (q, q, like, like),
        )
        pts += [(r["lat"], r["lon"]) for r in rows]

        # 3) 省级（admin1）别名 / 直接匹配
        a1 = self._q(
            "SELECT admin1 FROM aliases WHERE alias = ? AND kind='admin1' LIMIT 1",
            (q,),
        )
        admin1 = a1[0]["admin1"] if a1 else None
        if not admin1:
            a1 = self._q(
                "SELECT admin1 FROM aliases WHERE alias LIKE ? AND kind='admin1' LIMIT 1",
                (like,),
            )
            admin1 = a1[0]["admin1"] if a1 else None
        if admin1:
            rows = self._q(
                "SELECT lat, lon FROM places WHERE admin1 = ? OR admin1 LIKE ?",
                (admin1, admin1),
            )
            pts += [(r["lat"], r["lon"]) for r in rows]

        # 3b) 省级英文直接匹配（aliases 只有中文别名，英文输入如
        #     Xizang / Guangdong 走这里；0.7.8d 之前英文省名搜索无效）
        if not pts:
            rows = self._q(
                "SELECT lat, lon FROM places WHERE admin1 = ? LIMIT 5000", (q,))
            pts += [(r["lat"], r["lon"]) for r in rows]

        # 4) 国家级
        ccode = self._q(
            "SELECT country FROM aliases WHERE alias = ? AND kind='country' LIMIT 1",
            (q,),
        )
        country = ccode[0]["country"] if ccode else None
        if not country:
            ccode = self._q(
                "SELECT code FROM countries WHERE name = ? OR name LIKE ? LIMIT 1",
                (q, like),
            )
            country = ccode[0]["code"] if ccode else None
        if country:
            rows = self._q(
                "SELECT lat, lon FROM places WHERE country = ?", (country,)
            )
            pts += [(r["lat"], r["lon"]) for r in rows]

        if not pts:
            return None

        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        # 点集范围越小（城市级），周边 padding 越大，保证「在该城市拍的照」都能命中
        span = max(max(lats) - min(lats), max(lons) - min(lons))
        pad = 0.6 if span < 1.0 else (0.2 if span < 5.0 else 0.05)
        return (
            min(lats) - pad,
            max(lats) + pad,
            min(lons) - pad,
            max(lons) + pad,
        )


# 模块级单例（懒加载）
_coder: GeoCoder | None = None


def get_coder() -> GeoCoder:
    global _coder
    if _coder is None:
        _coder = GeoCoder()
    return _coder
