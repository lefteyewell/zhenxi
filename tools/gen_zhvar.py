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
"""生成 photo_manager/core/zhvar.py（繁简变体表，替代 zhconv）。

数据源：Unicode Unihan 数据库 Unihan_Variants.txt
  - 许可证：Unicode License（允许再分发，需署名）——无 GPL 纠缠
  - 下载：https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip
  - 用法：python tools/gen_zhvar.py [Unihan_Variants.txt 路径]
    （无参数时自动下载到临时目录）

生成逻辑：
1. kSimplifiedVariant：繁→简（一字可对多个简体，取首个为主映射）
2. kTraditionalVariant：简→繁（用于两件事）
   a. Unihan 把部分繁体映射到扩展区码位（如 癈→𬏮）时，反查是否有
      常用简体字以该繁体为其 kTraditionalVariant（如 废→癈），回退到常用字
   b. 补充 kSimplifiedVariant 未覆盖的繁简关系
3. 仅保留双方均在 BMP（U+0000-U+FFFF）的映射对——扩展区生僻字对
   搜索归一化无价值，且会造成非 BMP 目标映射
4. 简→繁多路展开表由繁→简表反转得到（一简对多繁全保留）
5. 少量高频一简对多繁字的主序人工指定（_PRIMARY，语言知识，非复制数据）

注意：不复制 zhconv 任何数据（GPLv2+）；短语级词汇（软体/滑鼠）不在
本表范围——搜索归一化不需要，显示转换应使用 OpenCC（Apache-2.0）。
"""

from __future__ import annotations

import os
import sys
import tempfile
import urllib.request
import zipfile

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "photo_manager", "core", "zhvar.py",
)
UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"

# 高频一简对多繁字的主序（首选繁体形）。语言知识整理，非复制任何 GPL 数据。
# 未列出的字按 Unihan 字段顺序。主序只影响封顶截断时的组合先后。
_PRIMARY = {
    "发": "發", "后": "後", "台": "臺", "干": "幹", "面": "麵", "钟": "鐘",
    "云": "雲", "里": "裡", "松": "鬆", "汇": "匯", "历": "歷", "复": "復",
    "尽": "盡", "系": "係", "表": "表", "只": "只", "帘": "帘", "才": "才",
    "丑": "丑", "出": "出", "谷": "谷", "划": "劃", "回": "回", "伙": "伙",
    "姜": "姜", "借": "借", "克": "克", "困": "困", "秋": "秋", "曲": "曲",
    "沈": "沈", "咸": "咸", "须": "須", "旋": "旋", "佣": "佣", "游": "游",
    "于": "於", "郁": "鬱", "御": "御", "岳": "岳", "志": "志", "注": "注",
    "准": "準", "周": "周", "板": "板", "布": "布", "卜": "卜", "漓": "漓",
    "熏": "熏", "折": "折", "征": "征", "症": "症", "致": "致", "制": "制",
}

# Unihan 变体数据库对 PRC 简化方案覆盖不全（缺 遊→游、錄→录 等常用对），
# 以下为人工整理的常用繁简对补充（语言知识，非复制任何 GPL 数据；
# 与 Unihan 重叠的条目已验证映射一致后剔除，仅保留 Unihan 真缺失项）。
# 键=繁体，值=简体。
_SUPPLEMENT = {
    "遊": "游", "錄": "录", "勳": "勋", "湧": "涌", "蠍": "蝎", "羨": "羡",
    "甕": "瓮", "絛": "绦", "妳": "你", "喦": "岩", "羶": "膻",
    "嶽": "岳", "佈": "布", "鹼": "碱",
}

# CJK 标点：查询侧剥离（附加变体，原文变体仍在，纯增益）
_PUNCT_STRIP = "，。、；：？！""''「」『』【】〔〕（）〈〉《》—…·～｜、　"

# 繁体组合展开封顶（含主序优先截断；典型查询 0-1 个多繁字，不会触顶）
_CAP = 6

# 地区词汇短语表：简体短语 -> 繁体变体元组（TW/HK 变体都收）。
# 收录原则：**只收字符级转换无法产生的形式**（字符级已正确的词不收，
# 避免与字符展开重复）；语言知识整理，非复制任何 GPL 数据。
# 覆盖：IT/数码、摄影影像、日常生活、饮食、交通、工作学习、医疗等域。
_PHRASES_S2T = {
    # IT/数码
    "软件": ("軟體", "軟件"), "硬件": ("硬體",), "网络": ("網路",),
    "服务器": ("伺服器",), "打印机": ("印表機",), "硬盘": ("硬碟",),
    "固态硬盘": ("固態硬碟",), "移动硬盘": ("行動硬碟",), "U盘": ("隨身碟",),
    "鼠标": ("滑鼠",), "内存": ("記憶體",), "显卡": ("顯示卡",),
    "主板": ("主機板",), "笔记本": ("筆記型電腦",), "智能手机": ("智慧型手機",),
    "分辨率": ("解析度",), "像素": ("畫素",), "激光": ("雷射",),
    "芯片": ("晶片",), "集成电路": ("積體電路",), "宽带": ("寬頻",),
    "打印": ("列印",), "光标": ("游標",), "菜单": ("選單",),
    "窗口": ("視窗",), "对话框": ("對話方塊",), "默认": ("預設",),
    "设置": ("設定",), "保存": ("儲存",), "文件": ("檔案",),
    "文件夹": ("資料夾",), "回收站": ("資源回收筒",), "剪贴板": ("剪貼簿",),
    "优化": ("最佳化",), "兼容": ("相容",), "激活": ("啟用",),
    "登录": ("登入",), "注销": ("登出",), "缓存": ("快取",),
    "客户端": ("用戶端",), "云计算": ("雲端計算",), "人工智能": ("人工智慧",),
    "智能": ("智慧",), "编程": ("程式設計",), "程序": ("程式",),
    "代码": ("程式碼",), "算法": ("演算法",), "函数": ("函式",),
    "变量": ("變數",), "对象": ("物件",), "数组": ("陣列",),
    "循环": ("迴圈",), "视频": ("影片",), "音频": ("音訊",),
    "光盘": ("光碟",), "存储卡": ("記憶卡",), "内存卡": ("記憶卡",),
    "读卡器": ("讀卡機",), "短信": ("簡訊",), "搜索引擎": ("搜尋引擎",),
    "掉线": ("斷線",), "粘贴": ("貼上",), "剪切": ("剪下",),
    "撤销": ("還原",), "重启": ("重新啟動",), "死机": ("當機",),
    "杀毒": ("防毒",), "黑客": ("駭客",), "恢复": ("復原", "還原"),
    "分区": ("分割區",), "磁盘": ("磁碟",), "数据线": ("傳輸線",),
    "屏幕": ("螢幕",), "字体": ("字型",), "加粗": ("粗體",),
    "下划线": ("底線",), "居中": ("置中",), "刷新": ("重新整理",),
    "主页": ("首頁",), "收藏夹": ("我的最愛",), "在线": ("線上",),
    "高清": ("高畫質",), "标清": ("標準畫質",), "视频通话": ("視訊通話",),
    "摄像头": ("攝影機",), "摄像机": ("攝影機",), "音箱": ("音響",),
    "充电宝": ("行動電源",), "墨盒": ("墨水匣",), "硒鼓": ("碳粉匣",),
    "存储": ("儲存",), "数码": ("數位",), "复印": ("影印",),
    "单反": ("單眼相機",), "二维码": ("二維條碼",),
    # 摄影影像
    "相册": ("相簿",), "水印": ("浮水印",), "壁纸": ("桌布",),
    "噪点": ("雜訊",), "点赞": ("按讚",), "截图": ("擷圖", "螢幕擷取"),
    "录屏": ("螢幕錄影",),
    # 日常生活
    "出租车": ("計程車", "的士"), "公交车": ("公車", "巴士"),
    "地铁": ("地鐵", "捷運"), "塑料": ("塑膠",), "方便面": ("泡麵", "公仔麵"),
    "幼儿园": ("幼稚園",), "站台": ("月台",), "身份证": ("身分證",),
    "工资": ("薪水", "人工"), "简历": ("履歷",), "应聘": ("應徵",),
    "外卖": ("外送",), "土豆": ("馬鈴薯",), "西红柿": ("番茄",),
    "菠萝": ("鳳梨",), "芝士": ("起司", "起士"), "结账": ("結帳",),
    "堵车": ("塞車",), "空调": ("空調", "冷氣機"), "冰箱": ("冰箱", "雪櫃"),
    "电梯": ("電梯", "升降機"), "沙发": ("沙發", "梳化"), "小区": ("社區",),
    "保安": ("警衛",), "保姆": ("保母",), "楼道": ("走廊",),
    "扶梯": ("電扶梯",), "区号": ("區碼",), "充值": ("加值", "儲值"),
    "信号": ("訊號",), "锁屏": ("鎖定螢幕",), "飞行模式": ("飛航模式",),
    "计算器": ("計算機",), "打车": ("叫車",), "拼车": ("共乘",),
    "驾校": ("駕訓班",), "年检": ("驗車",), "行驶证": ("行車執照",),
    "驾驶证": ("駕駛執照",), "违章": ("違規",), "追尾": ("追撞",),
    "拖车": ("拖吊車",), "红薯": ("地瓜",), "橙子": ("柳橙", "橘子"),
    "榴莲": ("榴槤",), "酸奶": ("優格", "優酪乳"), "维生素": ("維他命",),
    "药店": ("藥局",), "体检": ("健康檢查",), "B超": ("超音波",),
    "输液": ("打點滴",), "头疼": ("頭痛",), "肚子疼": ("肚子痛",),
    "牙疼": ("牙痛",),
    # 工作学习
    "班主任": ("班導師",), "导师": ("指導教授",), "橡皮": ("橡皮擦",),
    "圆珠笔": ("原子筆",), "练习册": ("練習簿",), "试卷": ("考卷",),
    "合同": ("合約",), "项目": ("專案",), "计划": ("計畫",),
    "营销": ("行銷",), "提成": ("佣金",),
    # 交通出行
    "登机牌": ("登機證",), "柜台": ("櫃檯",), "取款": ("提款",),
    "养老金": ("退休金",),
}


def fetch_unihan() -> str:
    """下载并解出 Unihan_Variants.txt，返回本地路径。"""
    tmp = tempfile.mkdtemp(prefix="unihan_")
    zpath = os.path.join(tmp, "Unihan.zip")
    print(f"下载 {UNIHAN_URL} ...", flush=True)
    urllib.request.urlretrieve(UNIHAN_URL, zpath)
    with zipfile.ZipFile(zpath) as zf:
        zf.extract("Unihan_Variants.txt", tmp)
    return os.path.join(tmp, "Unihan_Variants.txt")


def parse(path: str):
    """解析 Unihan_Variants.txt，返回 (trad->[simp...], simp->[trad...])。"""
    t2s: dict[str, list[str]] = {}
    s2t: dict[str, list[str]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or "\t" not in line:
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            cp = parts[0]
            if not cp.startswith("U+"):
                continue
            ch = chr(int(cp[2:], 16))
            field, values = parts[1], parts[2]
            if field == "kSimplifiedVariant":
                lst = t2s.setdefault(ch, [])
                for v in values.split():
                    c = chr(int(v[2:], 16))
                    if c not in lst:
                        lst.append(c)
            elif field == "kTraditionalVariant":
                lst = s2t.setdefault(ch, [])
                for v in values.split():
                    c = chr(int(v[2:], 16))
                    if c not in lst:
                        lst.append(c)
    return t2s, s2t


def build_pairs(t2s: dict[str, list[str]], s2t: dict[str, list[str]]):
    """构建最终繁→简映射对列表 [(繁, 简), ...]，BMP 优先 + 常用字回退。"""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(trad: str, simp: str) -> None:
        if trad == simp:
            return
        if ord(trad) > 0xFFFF or ord(simp) > 0xFFFF:
            return  # 仅保留 BMP 双方
        if trad in seen:
            return
        seen.add(trad)
        pairs.append((trad, simp))

    # 0) 人工补充表优先（Unihan 缺失的常用对）
    for trad, simp in _SUPPLEMENT.items():
        add(trad, simp)

    # 1) kSimplifiedVariant 主映射（跳过自引用变体，优先 BMP）
    for trad, simps in t2s.items():
        if not simps:
            continue
        primary = next(
            (v for v in simps if ord(v) <= 0xFFFF and v != trad), None)
        if primary is None:
            # 无可用 BMP 非自变体：反查以该繁体为 kTraditionalVariant 的常用简体字
            primary = next(
                (s for s, trads in s2t.items()
                 if trad in trads and ord(s) <= 0xFFFF and s != trad),
                None,
            )
            if primary is None:
                continue  # 共享字或无 BMP 目标，放弃
        add(trad, primary)
        # 其余 BMP 简体目标也保留（S2T 反转可多路命中）
        for s in simps:
            if s != primary and s != trad and ord(s) <= 0xFFFF \
                    and (trad, s) not in pairs:
                pairs.append((trad, s))

    # 2) kTraditionalVariant 反查补充（覆盖 kSimplifiedVariant 缺失的关系）
    for simp, trads in s2t.items():
        if ord(simp) > 0xFFFF:
            continue
        for trad in trads:
            add(trad, simp)

    # 稳定排序：按繁体码位（确定性输出）
    pairs.sort(key=lambda p: ord(p[0]))
    return pairs


def emit(pairs: list[tuple[str, str]]) -> str:
    """生成 zhvar.py 源码。"""
    import base64
    import zlib

    data = "".join(t + s for t, s in pairs)
    blob = base64.b85encode(zlib.compress(data.encode("utf-8"), 9)).decode("ascii")
    # 每 100 字符折行，保持源码可读
    lines = [blob[i:i + 100] for i in range(0, len(blob), 100)]
    blob_src = "\n".join(f'    "{ln}"' for ln in lines)

    primary_src = "\n".join(
        f'    "{k}": "{v}",' for k, v in sorted(_PRIMARY.items())
    )
    punct_src = "".join(_PUNCT_STRIP)
    def _fmt_variants(vs: tuple) -> str:
        """格式化为元组字面量；单元素元组必须带尾逗号（否则是裸字符串）。"""
        parts = ", ".join('"%s"' % v for v in vs)
        if len(vs) == 1:
            parts += ","
        return "(%s)" % parts

    phrases_src = "\n".join(
        '    "%s": %s,' % (k, _fmt_variants(vs))
        for k, vs in sorted(_PHRASES_S2T.items())
    )

    return f'''"""繁简归一化（0.5.60）：自实现字符级变体表 + 地区词汇短语表，替代 zhconv（GPLv2+）。

数据来源：
- 字符映射：Unicode Unihan 数据库（Unicode License）+ 少量人工补充对
- 短语表：人工整理的地区词汇（简→繁 TW/HK 变体，语言知识，非复制 GPL 数据）
生成脚本 tools/gen_zhvar.py 可复现。

设计定位：**搜索归一化**，不是显示转换——
- 繁→简：字符级全表（{len(pairs)} 对）
- 简→繁：一简对多繁**全展开**（如 发→發/髮、台→臺/檯/颱）——
  zhconv 对单个字符串只给一个最可能字形，搜索 OR 匹配会漏；
  本模块对查询做笛卡尔展开（封顶 {_CAP} 组，主序优先）
- 地区词汇短语：软件→軟體/軟件、网络→網路 等（{len(_PHRASES_S2T)} 条）——
  zhconv 短语级转换的对应能力，此处以"变体全展开"方式实现（召回更高）；
  繁体查询同样互通（軟件→软件/軟體）
- CJK 标点剥离：查询侧附加变体（原文变体仍在，纯增益），
  便于匹配 OCR 文本中夹带的全角标点
- 已知限制：短语表为人工精选，未覆盖全部地区词汇；
  显示转换请使用 OpenCC（Apache-2.0）

公开 API：
- to_simp(text) -> str            繁→简（短语感知，用于路径/关键词匹配）
- trad_variants(text, cap) -> list[str]   简→繁组合（主序优先，封顶）
- variants(text) -> list[str]      [原文, 简体, 短语变体, 繁体组合...] 去重保序
"""

from __future__ import annotations

import base64
import itertools
import zlib

_CAP = {_CAP}
_MAX_PHRASE_LEN = {max(len(k) for k in _PHRASES_S2T)}

# 繁→简映射对串（每 2 字符一对，按繁体码位排序；zlib+b85 压缩）
_PAIRS = zlib.decompress(base64.b85decode(
{blob_src}
)).decode("utf-8")

# 高频一简对多繁字的主序（生成时人工指定，语言知识）
_PRIMARY = {{
{primary_src}
}}

# 地区词汇短语表：简体短语 -> 繁体变体元组（TW/HK 都收；
# 只收字符级转换无法产生的形式，避免与字符展开重复）
_PHRASES_S2T = {{
{phrases_src}
}}

# 繁体短语 -> 简体（to_simp 用；同简体多繁体时保留先出现者）
_PHRASES_T2S = {{}}
for _s, _ts in _PHRASES_S2T.items():
    for _t in _ts:
        _PHRASES_T2S.setdefault(_t, _s)

# CJK 标点剥离集（查询侧）
_PUNCT = frozenset({punct_src!r})

_T2S: dict[str, str] = {{}}
_S2T: dict[str, list[str]] = {{}}
for _t, _s in zip(_PAIRS[0::2], _PAIRS[1::2]):
    _T2S.setdefault(_t, _s)  # 首次出现为主（生成器已排 BMP 优先在前）
    _lst = _S2T.setdefault(_s, [])
    if _t not in _lst:
        _lst.append(_t)
# 主序重排：指定首选繁体形置顶
for _s, _p in _PRIMARY.items():
    _lst = _S2T.get(_s)
    if _lst and _p in _lst:
        _lst.remove(_p)
        _lst.insert(0, _p)


def _find_phrases(text: str, table: dict) -> list[tuple[int, int, str]]:
    """最长匹配扫描短语（不重叠），返回 [(start, end, 短语)]。"""
    found = []
    i = 0
    n = len(text)
    while i < n:
        hit = None
        for L in range(min(_MAX_PHRASE_LEN, n - i), 1, -1):
            if text[i:i + L] in table:
                hit = (i, i + L, text[i:i + L])
                break
        if hit:
            found.append(hit)
            i = hit[1]
        else:
            i += 1
    return found


def to_simp(text: str) -> str:
    """繁→简（短语感知：先替换繁体短语，其余逐字转换；无映射原样保留）。"""
    if not text:
        return text
    out = []
    last = 0
    for st, en, tp in _find_phrases(text, _PHRASES_T2S):
        out.append("".join(_T2S.get(ch, ch) for ch in text[last:st]))
        out.append(_PHRASES_T2S[tp])
        last = en
    out.append("".join(_T2S.get(ch, ch) for ch in text[last:]))
    return "".join(out)


def _strip_punct(text: str) -> str:
    """剥离 CJK 标点（查询侧用；索引侧不动）。"""
    if not text:
        return text
    return "".join(ch for ch in text if ch not in _PUNCT)


def trad_variants(text: str, cap: int = _CAP) -> list[str]:
    """简→繁组合展开：每个字展开为其全部繁体变体，笛卡尔积封顶 cap 组。

    主序优先（_PRIMARY 指定 + Unihan 顺序），截断时保留最可能的字形组合。
    """
    if not text:
        return []
    lists = []
    for ch in text:
        vs = _S2T.get(ch)
        lists.append(vs if vs else [ch])
    out: list[str] = []
    for combo in itertools.product(*lists):
        s = "".join(combo)
        if s not in out:
            out.append(s)
            if len(out) >= cap:
                break
    return out


def _phrase_forms(text: str, cap: int = 6) -> list[str]:
    """短语替换形：全短语变体笛卡尔组合（主序优先）+ 单短语替换形。

    单短语替换形保留其余简体字，供 trad_variants 补全其余字的繁体形，
    从而覆盖"短语繁体 + 其余字繁体"的文档形态（如 軟體設置）。
    """
    found = _find_phrases(text, _PHRASES_S2T)
    if not found:
        return []
    forms: list[str] = []
    for combo in itertools.product(*[_PHRASES_S2T[p] for _, _, p in found]):
        s = text
        for (st, en, _), v in zip(reversed(found), reversed(combo)):
            s = s[:st] + v + s[en:]
        if s not in forms:
            forms.append(s)
        if len(forms) >= cap:
            return forms
    for st, en, p in found:
        for v in _PHRASES_S2T[p]:
            s = text[:st] + v + text[en:]
            if s not in forms:
                forms.append(s)
                if len(forms) >= cap:
                    return forms
    return forms


def variants(text: str) -> list[str]:
    """搜索变体展开：[原文, 简体, 短语变体, 繁体组合...] 去重保序。

    与 zhconv 方案的差异（有意）：
    - zhconv 给 [原文, 简体, 繁体] 三个（繁体只一个最可能字形）；
    - 本实现：繁体侧做一简对多繁全展开 + 地区词汇短语变体（封顶），召回更高。
    """
    if not text:
        return []
    core = _strip_punct(text)
    out = [text]
    base = to_simp(core)  # 简体基准（短语感知；繁/简输入归一到同一基准）
    if base and base not in out:
        out.append(base)
    # 短语替换形（地区词汇互通）+ 其 char-level 补全展开
    for pf in _phrase_forms(base):
        if pf not in out:
            out.append(pf)
        for v in trad_variants(pf, cap=2):
            if v not in out:
                out.append(v)
    # 简体基准的 char-level 繁体展开（多繁字）
    for v in trad_variants(base, cap=_CAP):
        if v not in out:
            out.append(v)
    return out
'''


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else fetch_unihan()
    print(f"解析 {path} ...", flush=True)
    t2s, s2t = parse(path)
    print(f"  kSimplifiedVariant 繁体字数: {len(t2s)}")
    print(f"  kTraditionalVariant 简体字数: {len(s2t)}")
    pairs = build_pairs(t2s, s2t)
    multi = sum(1 for _, simps in s2t.items() if len(simps) > 1)
    print(f"  生成映射对: {len(pairs)}（一简对多繁字: {multi}）")
    print(f"  地区词汇短语: {len(_PHRASES_S2T)} 条")

    src = emit(pairs)
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    print(f"已生成 {OUT_PATH}（{len(src) / 1024:.1f} KB）")

    # 与 zhconv 对比（若已安装）
    try:
        from zhconv.zhconv import convert as zc
    except Exception:
        print("（zhconv 未安装，跳过对比）")
        return 0
    agree = diff = 0
    samples = []
    for trad, simp in pairs:
        if len(trad) == 1 and len(simp) == 1:
            z = zc(trad, "zh-cn")
            if z == simp:
                agree += 1
            else:
                diff += 1
                if len(samples) < 10:
                    samples.append((trad, simp, z))
    print(f"  与 zhconv 单字映射对比: 一致 {agree} / 不一致 {diff}")
    for t, s, z in samples:
        print(f"    {t}: zhvar={s} zhconv={z}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
