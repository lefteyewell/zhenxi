#!/usr/bin/env python3
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
"""生成离线地理数据库 models/geo/geo.sqlite（反向地理编码用）。

数据源（均 CC BY 4.0，© GeoNames）：
  - cities1000.zip       全球 ~13 万城市（名称/经纬度/国家/省/人口）
  - admin1CodesASCII.txt 省/州代码 → 名称
  - countryInfo.txt      国家代码 → 名称
  - 中文别名（省/市/景点）为内置精选数据集，可随时扩展。

完全离线运行；仅在「生成数据库」这一步联网下载一次原始数据（可复用已下载文件）。
产物 models/geo/geo.sqlite 不随 git 提交（.gitignore 已忽略 models/）。

用法：
    python tools/build_geo.py
"""
from __future__ import annotations

import io
import os
import sqlite3
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(ROOT, "models", "geo")
ZIP_PATH = os.path.join(GEO, "cities1000.zip")
ADM1_PATH = os.path.join(GEO, "admin1CodesASCII.txt")
CTRY_PATH = os.path.join(GEO, "countryInfo.txt")
DB_PATH = os.path.join(GEO, "geo.sqlite")

UA = {"User-Agent": "photo-manager build_geo/1.0 (+offline geocoder)"}


def _fetch(url: str, dest: str) -> None:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"  · 复用已下载：{os.path.basename(dest)}")
        return
    print(f"  · 下载 {url}")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())
    print(f"    完成 {os.path.basename(dest)} ({os.path.getsize(dest)} 字节)")


def _readlines(path: str):
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            yield line


# ---- 中文别名数据集（精选，可扩展） ----

# 34 个省级行政区：中文名 → GeoNames admin1 ascii 名
CN_PROVINCES = {
    "北京": "Beijing", "天津": "Tianjin", "河北": "Hebei", "山西": "Shanxi",
    "内蒙古": "Inner Mongolia", "辽宁": "Liaoning", "吉林": "Jilin",
    "黑龙江": "Heilongjiang", "上海": "Shanghai", "江苏": "Jiangsu",
    "浙江": "Zhejiang", "安徽": "Anhui", "福建": "Fujian", "江西": "Jiangxi",
    "山东": "Shandong", "河南": "Henan", "湖北": "Hubei", "湖南": "Hunan",
    "广东": "Guangdong", "广西": "Guangxi", "海南": "Hainan", "重庆": "Chongqing",
    "四川": "Sichuan", "贵州": "Guizhou", "云南": "Yunnan", "西藏": "Tibet",
    "陕西": "Shaanxi", "甘肃": "Gansu", "青海": "Qinghai", "宁夏": "Ningxia",
    "新疆": "Xinjiang", "香港": "Hong Kong", "澳门": "Macau", "台湾": "Taiwan",
}

# 主要城市：中文名 → GeoNames ascii 名（约 130 个）
CN_CITIES = {
    "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou", "深圳": "Shenzhen",
    "天津": "Tianjin", "重庆": "Chongqing", "杭州": "Hangzhou", "南京": "Nanjing",
    "苏州": "Suzhou", "成都": "Chengdu", "武汉": "Wuhan", "西安": "Xian",
    "沈阳": "Shenyang", "大连": "Dalian", "青岛": "Qingdao", "济南": "Jinan",
    "厦门": "Xiamen", "福州": "Fuzhou", "昆明": "Kunming", "贵阳": "Guiyang",
    "长沙": "Changsha", "郑州": "Zhengzhou", "哈尔滨": "Harbin",
    "长春": "Changchun", "石家庄": "Shijiazhuang", "太原": "Taiyuan",
    "合肥": "Hefei", "南昌": "Nanchang", "南宁": "Nanning", "海口": "Haikou",
    "兰州": "Lanzhou", "乌鲁木齐": "Urumqi", "拉萨": "Lhasa", "西宁": "Xining",
    "银川": "Yinchuan", "呼和浩特": "Hohhot", "香港": "Hong Kong", "澳门": "Macau",
    "台北": "Taipei", "高雄": "Kaohsiung", "无锡": "Wuxi", "宁波": "Ningbo",
    "温州": "Wenzhou", "佛山": "Foshan", "东莞": "Dongguan", "珠海": "Zhuhai",
    "中山": "Zhongshan", "惠州": "Huizhou", "嘉兴": "Jiaxing", "绍兴": "Shaoxing",
    "常州": "Changzhou", "南通": "Nantong", "徐州": "Xuzhou", "扬州": "Yangzhou",
    "镇江": "Zhenjiang", "连云港": "Lianyungang", "台州": "Taizhou",
    "金华": "Jinhua", "泉州": "Quanzhou", "漳州": "Zhangzhou", "烟台": "Yantai",
    "潍坊": "Weifang", "临沂": "Linyi", "淄博": "Zibo", "威海": "Weihai",
    "洛阳": "Luoyang", "开封": "Kaifeng", "桂林": "Guilin", "三亚": "Sanya",
    "北海": "Beihai", "大理": "Dali", "丽江": "Lijiang",
    "张家界": "Zhangjiajie", "黄山": "Huangshan", "九江": "Jiujiang",
    "包头": "Baotou", "鄂尔多斯": "Ordos", "大同": "Datong",
    "呼伦贝尔": "Hulunbuir", "齐齐哈尔": "Qiqihar", "鞍山": "Anshan",
    "锦州": "Jinzhou", "蚌埠": "Bengbu", "芜湖": "Wuhu", "马鞍山": "Ma'anshan",
    "安庆": "Anqing", "赣州": "Ganzhou", "宜昌": "Yichang", "襄阳": "Xiangyang",
    "十堰": "Shiyan", "株洲": "Zhuzhou", "湘潭": "Xiangtan", "衡阳": "Hengyang",
    "岳阳": "Yueyang", "汕头": "Shantou", "湛江": "Zhanjiang", "柳州": "Liuzhou",
    "绵阳": "Mianyang", "宜宾": "Yibin", "泸州": "Luzhou", "南充": "Nanchong",
    "遵义": "Zunyi", "咸阳": "Xianyang", "宝鸡": "Baoji", "天水": "Tianshui",
    "玉树": "Yushu", "喀什": "Kashgar", "阿克苏": "Aksu", "吐鲁番": "Turpan",
    "克拉玛依": "Karamay", "延安": "Yan'an", "景德镇": "Jingdezhen",
    "日喀则": "Shigatse", "伊犁": "Yili", "曲阜": "Qufu", "秦皇岛": "Qinhuangdao",
    "唐山": "Tangshan", "廊坊": "Langfang", "保定": "Baoding",
    "盐城": "Yancheng", "泰州": "Taizhou", "湖州": "Huzhou", "衢州": "Quzhou",
    "丽水": "Lishui",
}

# 著名摄影景点：中文名 → (纬度, 经度)
CN_LANDMARKS = {
    "西湖": (30.2447, 120.1486), "故宫": (39.9163, 116.3972),
    "紫禁城": (39.9163, 116.3972), "天安门": (39.9055, 116.3976),
    "八达岭长城": (40.4319, 116.5704), "长城": (40.4319, 116.5704),
    "外滩": (31.2397, 121.4905), "东方明珠": (31.2397, 121.4998),
    "兵马俑": (34.3853, 109.2734), "黄山": (30.1318, 118.1616),
    "张家界": (29.3170, 110.4790), "九寨沟": (33.2603, 103.9180),
    "布达拉宫": (29.6558, 91.1170), "鼓浪屿": (24.4470, 118.0660),
    "丽江古城": (26.8721, 100.2299), "洱海": (25.7837, 100.1833),
    "千岛湖": (29.6057, 119.0226), "漓江": (25.2736, 110.2900),
    "桂林山水": (25.2736, 110.2900), "泰山": (36.2522, 117.1016),
    "华山": (34.4817, 110.0857), "少林寺": (34.5068, 112.9356),
    "嵩山": (34.5068, 112.9356), "莫高窟": (40.0351, 94.8090),
    "平遥古城": (37.2012, 112.1785), "周庄": (31.1120, 120.8530),
    "西塘": (30.9450, 120.8910), "宏村": (29.9108, 117.9950),
    "喀纳斯": (48.7050, 87.0450), "青海湖": (36.7833, 100.1667),
    "茶卡盐湖": (36.5833, 99.3833), "亚龙湾": (18.2150, 109.6330),
    "天涯海角": (18.2670, 109.7500), "黄龙": (32.7550, 103.8330),
    "武当山": (32.4080, 111.0050), "普陀山": (30.0090, 122.3880),
    "峨眉山": (29.5170, 103.3360), "都江堰": (31.0020, 103.6170),
}


def build():
    os.makedirs(GEO, exist_ok=True)
    _fetch("https://download.geonames.org/export/dump/cities1000.zip",
           ZIP_PATH)
    _fetch("https://download.geonames.org/export/dump/admin1CodesASCII.txt",
           ADM1_PATH)
    _fetch("https://download.geonames.org/export/dump/countryInfo.txt",
           CTRY_PATH)

    # admin1 代码 → 名称
    adm1 = {}
    for line in _readlines(ADM1_PATH):
        parts = line.split("\t")
        if len(parts) >= 2:
            adm1[parts[0]] = parts[1]

    # 国家代码 → 名称
    countries = {}
    for line in _readlines(CTRY_PATH):
        parts = line.split("\t")
        if len(parts) >= 4 and parts[0]:
            countries[parts[0]] = parts[4]

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE places(
            geoname_id INTEGER PRIMARY KEY,
            name TEXT, ascii_name TEXT, country TEXT, admin1 TEXT,
            admin2 TEXT, lat REAL, lon REAL, feature TEXT, population INTEGER
        )"""
    )
    conn.execute(
        "CREATE TABLE aliases("
        "geoname_id INTEGER, alias TEXT NOT NULL, kind TEXT NOT NULL, "
        "admin1 TEXT, country TEXT)"
    )
    conn.execute("CREATE TABLE countries(code TEXT PRIMARY KEY, name TEXT)")
    conn.execute("CREATE INDEX idx_places_lat ON places(lat)")
    conn.execute("CREATE INDEX idx_places_lon ON places(lon)")
    conn.execute("CREATE INDEX idx_places_admin1 ON places(admin1)")
    conn.execute("CREATE INDEX idx_alias ON aliases(alias)")

    # 解析 cities1000
    n = 0
    with zipfile.ZipFile(ZIP_PATH) as z:
        name = [x for x in z.namelist() if x.endswith(".txt")][0]
        with z.open(name) as fh:
            text = fh.read().decode("utf-8", "replace")
    for line in text.splitlines():
        if not line.strip():
            continue
        p = line.split("\t")
        if len(p) < 15:
            continue
        gid = int(p[0])
        cname = p[1]
        aname = p[2]
        lat = float(p[4])
        lon = float(p[5])
        fcode = p[7]
        ccode = p[8]
        adm1code = p[10]
        pop = int(p[14]) if p[14].isdigit() else 0
        full = f"{ccode}.{adm1code}" if adm1code else ""
        adm1name = adm1.get(full, adm1code)
        conn.execute(
            "INSERT OR IGNORE INTO places VALUES(?,?,?,?,?,?,?,?,?,?)",
            (gid, cname, aname, ccode, adm1name, "", lat, lon, fcode, pop),
        )
        n += 1

    conn.commit()  # 先提交城市数据，避免后续别名步骤异常导致整体回滚

    for code, cname in countries.items():
        conn.execute("INSERT OR IGNORE INTO countries VALUES(?,?)",
                     (code, cname))

    # 中文别名：省级
    for zh, ascii1 in CN_PROVINCES.items():
        conn.execute(
            "INSERT INTO aliases(geoname_id, alias, kind, admin1, country) "
            "VALUES(NULL,?, 'admin1', ?, 'CN')", (zh, ascii1))
    # 中文别名：城市级（解析为 geoname_id）
    city_hits = 0
    city_miss = []
    for zh, ascii1 in CN_CITIES.items():
        row = conn.execute(
            "SELECT geoname_id FROM places WHERE ascii_name=?", (ascii1,)
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT geoname_id FROM places WHERE ascii_name LIKE ? "
                "ORDER BY population DESC LIMIT 1", (ascii1 + "%",)
            ).fetchone()
        if row:
            conn.execute(
                "INSERT INTO aliases(geoname_id, alias, kind) VALUES(?,?, 'city')",
                (row[0], zh))
            city_hits += 1
        else:
            city_miss.append(ascii1)
    # 中文别名：景点（插入为独立 place + landmark 别名）
    lm_id = -1
    for zh, (lat, lon) in CN_LANDMARKS.items():
        conn.execute(
            "INSERT INTO places VALUES(?,?,?,?,?,?,?,?,?,?)",
            (lm_id, zh, zh, "CN", "", "", lat, lon, "LM", 0))
        conn.execute(
            "INSERT INTO aliases(geoname_id, alias, kind) VALUES(?,?, 'landmark')",
            (lm_id, zh))
        lm_id -= 1

    conn.commit()
    cnt = conn.execute("SELECT COUNT(*) FROM places").fetchone()[0]
    acnt = conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
    conn.close()
    print(f"完成：places={cnt} 条，aliases={acnt} 条（城市命中 {city_hits}，"
          f"未命中 {len(city_miss)}：{','.join(city_miss[:10])}...）")
    print(f"数据库：{DB_PATH}  ({os.path.getsize(DB_PATH)/1024/1024:.1f} MB)")


if __name__ == "__main__":
    try:
        build()
    except Exception as e:  # noqa
        print("构建失败：", repr(e), file=sys.stderr)
        sys.exit(1)
