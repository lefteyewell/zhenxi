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
"""半自动场景建议（0.5.27）：发现词表未覆盖的照片簇并建议新场景词。

流程：图像向量 → 与现有词表文本向量比对找"未覆盖"照片 → 领头聚类（纯 numpy、
确定性、无第三方依赖）→ 对足够大的簇用内置候选池零样本挑名 → 输出建议。

设计原则（对应"竞争式排名脆弱性"的结论）：
- 词表质量由人把关：本模块只**建议**，采纳与否由用户在工具中心勾选确认，
  确认后经追加合并语义（autotag.resolve_scene_vocab）写入 sceneTags；
- 只读分析：不写库、不改任何数据；
- 降级安全：无 CLIP 模型 / 无语义向量 / 词表为空时返回 ok=False，不抛错。
"""
from __future__ import annotations

from photo_manager.core.db import Database

# 未覆盖判定：照片与现有词表所有词的最大相似度低于该值 → 未被词表覆盖
# （与 autotag.CLIP_SIM_THRESHOLD 对齐）
UNCOVERED_SIM = 0.20
# 领头聚类半径：与某簇领头的余弦相似度 ≥ 该值即归入该簇
CLUSTER_RADIUS = 0.82
# 簇最小照片数：小于该值不产生建议（避免给三五张照片新增一个词）
MIN_CLUSTER = 5
# 最多返回的建议数 / 最多形成的簇数（防止大库产生过多候选）
MAX_SUGGEST = 8
MAX_LEADERS = 32
# 建议词与现有词表词的文本相似度上限：超过视为近重复，不建议
NEAR_DUP_SIM = 0.85

# 建议候选池（0.5.27）：摄影向场景词，刻意避开内置 SCENE_CLIP_TAGS 已有词。
# 候选池只是"取名素材"，不直接进词表；覆盖率不足时按真机效果扩充。
SUGGEST_POOL: tuple[str, ...] = (
    # 自然
    "星空", "银河", "极光", "云海", "草原", "峡谷", "瀑布", "湖泊", "河流", "湿地",
    "海滩", "礁石", "田园", "梯田", "花田", "红叶", "樱花", "荷花", "薰衣草", "向日葵",
    # 场所
    "古镇", "古城", "庙宇", "寺院", "教堂", "城墙", "园林", "公园", "广场", "游乐园",
    "水族馆", "植物园", "动物园", "美术馆", "展览馆", "图书馆",
    # 生活
    "咖啡馆", "茶馆", "餐厅", "厨房", "夜市", "市集", "商场", "书店", "剧院", "电影院",
    # 工作与教育
    "办公室", "车间", "工厂", "仓库", "工地", "实验室", "医院", "教室", "校园", "操场",
    # 运动休闲
    "健身房", "游泳池", "球场", "滑雪场", "溜冰场", "马拉松", "骑行", "登山", "徒步",
    "冲浪", "潜水", "钓鱼", "瑜伽", "舞蹈",
    # 交通
    "机场", "高铁站", "火车站", "码头", "港口", "公路", "隧道", "桥梁", "停车场",
    # 节庆
    "烟花", "灯会", "庙会", "花灯", "舞龙", "舞狮", "龙舟", "巡游", "跨年",
    # 动植物
    "鸟类", "野生动物", "昆虫", "马匹", "羊群", "牛群", "海豚", "鲸鱼",
    # 摄影手法
    "航拍", "微距", "剪影", "倒影", "长曝光", "黑白",
)


def _l2(mat):
    """行归一化（零向量保持原样，避免除零）。"""
    import numpy as np

    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def leader_cluster(mat, radius: float = CLUSTER_RADIUS,
                   max_leaders: int = MAX_LEADERS) -> list[list[int]]:
    """领头聚类：按行序贪心，与已有领头相似度 ≥ radius 归入该簇，否则自立新簇。

    确定性（同输入同输出）、只依赖 numpy、O(N·簇数)。
    返回簇列表（每簇为行号列表）；被 max_leaders 截断的剩余行归入最近的簇
    （不足 radius 也不新建，避免尾部碎簇）。
    """
    import numpy as np

    n = mat.shape[0]
    leaders: list[np.ndarray] = []
    clusters: list[list[int]] = []
    for i in range(n):
        v = mat[i]
        best, best_sim = -1, -1.0
        for ci, lv in enumerate(leaders):
            s = float(lv @ v)
            if s > best_sim:
                best, best_sim = ci, s
        if best >= 0 and best_sim >= radius:
            clusters[best].append(i)
        elif len(leaders) < max_leaders:
            leaders.append(v)
            clusters.append([i])
        elif best >= 0:
            clusters[best].append(i)
        else:  # 理论不可达（n>0 且 max_leaders≥1），防御
            break
    return [c for c in clusters if c]


def suggest_scenes(db: Database, svc=None, vocab=None) -> dict:
    """分析词表未覆盖的照片簇，返回场景建议。

    :param vocab: 当前场景词表（None 则用内置 SCENE_CLIP_TAGS）；
                  调用方（bridge）应传合并后的最终词表。
    返回 {"ok": bool, "reason": str?, "scanned": int, "uncovered": int,
          "suggestions": [{"word", "count", "examples": [photo_id...]}]}
    """
    import numpy as np

    from photo_manager.core.autotag import SCENE_CLIP_TAGS
    from photo_manager.core.clip import ClipUnavailable, MODEL_ID, get_service

    try:
        svc = svc or get_service()
        if not svc.available:
            return {"ok": False, "reason": "model_missing", "suggestions": []}
    except Exception:
        return {"ok": False, "reason": "model_missing", "suggestions": []}

    vocab = list(vocab) if vocab else list(SCENE_CLIP_TAGS)
    if not vocab:
        return {"ok": False, "reason": "no_tags", "suggestions": []}

    try:
        vocab_vecs = np.stack([svc.encode_text(t) for t in vocab]).astype(np.float32)
        pool_vecs = np.stack([svc.encode_text(w) for w in SUGGEST_POOL]).astype(np.float32)
    except (ClipUnavailable, Exception):
        return {"ok": False, "reason": "model_missing", "suggestions": []}
    vocab_vecs = _l2(vocab_vecs)
    pool_vecs = _l2(pool_vecs)

    # 分块读取向量（大库不一次性载入）
    ids: list[int] = []
    chunks: list[np.ndarray] = []
    last = 0
    while True:
        rows = db.conn.execute(
            "SELECT photo_id, embedding FROM photo_embeddings "
            "WHERE model = ? AND photo_id > ? ORDER BY photo_id LIMIT 5000",
            (MODEL_ID, last),
        ).fetchall()
        if not rows:
            break
        last = rows[-1][0]
        ids.extend(r[0] for r in rows)
        chunks.append(np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows]))
    if not ids:
        return {"ok": False, "reason": "no_embeddings", "scanned": 0,
                "uncovered": 0, "suggestions": []}
    mat = _l2(np.concatenate(chunks, axis=0))

    # 未覆盖判定：与词表所有词的最大相似度过低
    max_sim = (mat @ vocab_vecs.T).max(axis=1)
    uncovered = np.where(max_sim < UNCOVERED_SIM)[0]
    if len(uncovered) == 0:
        return {"ok": True, "scanned": len(ids), "uncovered": 0, "suggestions": []}

    # 领头聚类 + 过小簇过滤
    clusters = [c for c in leader_cluster(mat[uncovered]) if len(c) >= MIN_CLUSTER]
    clusters.sort(key=len, reverse=True)

    # 近重复过滤矩阵：候选池 × 现有词表
    dup = pool_vecs @ vocab_vecs.T  # (P, V)
    vocab_set = set(vocab)
    suggestions: list[dict] = []
    for c in clusters[: MAX_SUGGEST * 3]:
        member_rows = uncovered[np.asarray(c)]
        mean = _l2(mat[member_rows].mean(axis=0).reshape(1, -1))[0]
        cand = pool_vecs @ mean
        word = ""
        for j in np.argsort(-cand):
            w = SUGGEST_POOL[j]
            if w in vocab_set or float(dup[j].max()) >= NEAR_DUP_SIM:
                continue
            word = w
            break
        if not word:
            continue
        # 示例照片：取簇内与簇心最接近的前 6 张
        inner = mat[member_rows] @ mean
        top6 = [ids[member_rows[k]] for k in np.argsort(-inner)[:6]]
        suggestions.append({"word": word, "count": len(c), "examples": top6})
        if len(suggestions) >= MAX_SUGGEST:
            break

    return {"ok": True, "scanned": len(ids), "uncovered": int(len(uncovered)),
            "suggestions": suggestions}
