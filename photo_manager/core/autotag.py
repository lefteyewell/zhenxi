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
"""场景自动标签：CLIP 零样本（图像内容）+ 路径/文件名关键词兜底。

优先级：CLIP 零样本场景标签（图像内容识别，解决"标签太少"痛点）>
路径/文件名关键词（兜底，离线无模型或向量缺失时仍可用）。
低风险：只新增 photo_tags 行，不改不删现有数据；规则可增量扩展。
"""
from __future__ import annotations

import logging

from photo_manager.core.db import Database

log = logging.getLogger(__name__)

# 关键词 → 标签。匹配目录/文件名中含关键词的场景（兜底用，规则谨慎）。
SCENE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "旅行": ("旅行", "旅游", "海边", "远行", "出行", "游记"),
    "风景": ("风景", "海边", "山水", "雪山", "日落", "夕阳", "自然"),
    "写真": ("写真", "人像", "人物", "模特", "棚拍"),
    "年会": ("年会", "庆典", "颁奖"),
    "聚餐": ("聚餐", "宴会", "酒会", "晚宴"),
    "发布会": ("发布会", "路演", "展示会"),
    "宠物": ("宠物", "狗狗", "猫咪", "猫猫"),
    "美食": ("美食", "餐厅", "咖啡", "下午茶", "甜品"),
    "建筑": ("建筑", "城市", "街景", "地标"),
    "运动": ("运动", "健身", "马拉松", "骑行", "球赛"),
    "节日": ("节日", "圣诞", "跨年", "春节", "元宵", "中秋"),
}

# 摄影向零样本场景标签候选（用 CLIP 文本编码器 "一张{}的照片" 模板编码）。
# 既作为场景标签写入库，也作为自由语义搜索的基础词表。
SCENE_CLIP_TAGS: tuple[str, ...] = (
    "风景", "海边", "雪山", "山水", "城市", "建筑", "夜景", "人像",
    "聚会", "会议", "演讲", "婚礼", "宠物", "美食", "运动", "旅行",
    "日落", "日出", "花卉", "动物", "街拍", "儿童", "毕业", "演出",
    "天空", "森林", "沙漠", "博物馆", "室内",
)
# 自动场景标签统一挂在「场景」父节点下（如「场景/海边」），与用户手打的顶层标签区分开；
# 配合层级标签树，搜索 tag:场景 即可一次看全部场景照片。root 置空则退化为扁平标签。
SCENE_TAG_ROOT = "场景"

CLIP_TOP_K = 3          # 每张照片最多打几个场景标签
CLIP_SIM_THRESHOLD = 0.20  # 余弦相似度阈值，低于不打（badcase 由关键词兜底）
# 注：阈值需在真机（有 727MB 模型）上按效果微调；当前为保守初值。


def parse_custom_tags(text: str | None) -> list[str]:
    """解析用户自定义场景词表（逗号/换行/中文逗号分隔），保留顺序与「-」排除前缀。

    0.5.27 起自定义词表语义为**追加合并**：正常项追加到内置词表，
    「-词」表示从内置词表中排除该词（见 resolve_scene_vocab）。
    """
    items = str(text or "").replace("\n", ",").replace("，", ",").split(",")
    return [t.strip() for t in items if t.strip()]


def resolve_scene_vocab(text: str | None) -> list[str]:
    """解析最终 CLIP 场景词表（0.5.27 追加合并语义）。

    规则：
    - 基线是内置 SCENE_CLIP_TAGS；
    - 自定义正常项（如「星空」）追加到内置词表之后（去重、保序）；
    - 自定义「-词」从内置词表中排除该词（排除优先于追加，即「-宠物 宠物」结果不含宠物）；
    - 未配置或只写排除时，结果就是内置词表（或其排除后子集）——
      「只想加一个词」永远安全，不再有旧版整体替换导致内置词全失效的坑。

    返回词表列表（可能为空=用户把所有词都排除了，此时 auto_tag_clip 不打任何标签）。
    """
    custom = parse_custom_tags(text)
    excluded = {t[1:].strip() for t in custom if t.startswith("-") and len(t) > 1}
    added = [t for t in custom if not t.startswith("-") and t not in SCENE_CLIP_TAGS]
    return [t for t in SCENE_CLIP_TAGS if t not in excluded] + added


def merge_custom_words(text: str | None, new_words) -> tuple[str, int]:
    """把（场景建议勾选等来源的）新词并入自定义词表文本，返回 (新文本, 实际新增数)。

    追加合并语义（0.5.27）：
    - 与已有自定义词去重（已存在的词不重复写入）；
    - 若某词此前被「-词」排除，加入视为推翻排除（移除排除项并加入该词）；
    - 原有内容（含其它排除项）保持顺序不变，新词追加在尾部。
    """
    new = [str(w).strip() for w in (new_words or []) if str(w).strip()]
    cur = parse_custom_tags(text)
    new_set = set(new)
    kept = [t for t in cur if not (t.startswith("-") and t[1:] in new_set)]
    added = [w for w in new if w not in kept]
    return ", ".join(kept + added), len(added)


def _keyword_tags(db: Database, root: str = SCENE_TAG_ROOT) -> int:
    """路径/文件名关键词兜底打标（写入 root 层级下）。返回新增数。

    路径匹配做繁简归一化（0.5.25）：繁体路径与简体关键词互相命中。
    0.5.59：改用自实现 zhvar（替代 zhconv，见 core/zhvar.py）。
    """
    conn = db.conn
    from photo_manager.core.zhvar import to_simp
    existing = {
        (pid, tag)
        for pid, tag in conn.execute("SELECT photo_id, tag FROM photo_tags").fetchall()
    }
    added = 0
    for pid, path in conn.execute("SELECT id, file_path FROM photos WHERE media_type='photo'"):
        low = path.replace("\\", "/").lower()
        low_norm = to_simp(low).lower()
        for tag, kws in SCENE_KEYWORDS.items():
            full = f"{root}/{tag}" if root else tag
            if (pid, full) in existing:
                continue
            for kw in kws:
                if kw in low or kw in low_norm:
                    conn.execute(
                        "INSERT INTO photo_tags(photo_id, tag) VALUES (?,?)"
                        " ON CONFLICT(photo_id, tag) DO NOTHING",
                        (pid, full),
                    )
                    added += 1
                    break
    conn.commit()
    return added


def auto_tag_clip(db: Database, svc=None, tags=None,
                  root: str = SCENE_TAG_ROOT) -> dict:
    """CLIP 零样本场景标签：用已存的图像向量与场景标签文本向量算相似度，top-k 写入。

    写入的标签带 root 前缀（默认「场景/海边」），便于在层级标签树里集中浏览。
    :param tags: 自定义场景词表（None 则用 SCENE_CLIP_TAGS）
    依赖 photo_embeddings 表（需先执行 clip-index 生成图像向量）；若模型缺失或某照片无向量，
    则该照片跳过（不报错）。返回统计 {added, clip, scanned}。
    """
    import numpy as np

    from photo_manager.core.clip import MODEL_ID, ClipUnavailable, get_service

    tag_list = [str(t).strip() for t in (tags or SCENE_CLIP_TAGS) if str(t).strip()]
    if not tag_list:
        return {"added": 0, "clip": False, "reason": "no_tags"}

    svc = svc or get_service()
    if not svc.available:
        # 模型缺失：交由关键词兜底，不在此报错
        return {"added": 0, "clip": False, "reason": "model_missing"}

    try:
        # 场景标签文本向量（一次性缓存）；文本编码用短名，模板「一张{}的照片」
        tag_vecs = np.stack([svc.encode_text(t) for t in tag_list])  # (N,512)
    except ClipUnavailable:
        return {"added": 0, "clip": False, "reason": "model_missing"}

    full_tags = [f"{root}/{t}" if root else t for t in tag_list]
    # 接受 Database 或裸 sqlite3 连接（0.5.49：clip 后台任务改用独立连接，
    # 避免与主线程 UI 查询共用连接触发 pysqlite 语句缓存竞态）
    conn = getattr(db, "conn", db)
    placeholders = ",".join("?" * len(full_tags))
    rows = conn.execute(
        "SELECT p.id, e.embedding FROM photos p "
        "JOIN photo_embeddings e ON e.photo_id = p.id AND e.model = ? "
        "WHERE p.id NOT IN (SELECT photo_id FROM photo_tags WHERE tag IN (%s))"
        % placeholders,
        (MODEL_ID, *full_tags),
    ).fetchall()
    added = 0
    for pid, blob in rows:
        vec = np.frombuffer(blob, dtype=np.float32)
        sims = tag_vecs @ vec
        order = np.argsort(-sims)[:CLIP_TOP_K]
        for idx in order:
            if float(sims[idx]) >= CLIP_SIM_THRESHOLD:
                conn.execute(
                    "INSERT INTO photo_tags(photo_id, tag) VALUES (?,?)"
                    " ON CONFLICT(photo_id, tag) DO NOTHING",
                    (pid, full_tags[idx]),
                )
                added += 1
    conn.commit()
    return {"added": added, "clip": True, "scanned": len(rows)}


def auto_tag_library(db: Database, tags=None) -> dict:
    """为照片补场景标签：先关键词兜底，再 CLIP 零样本（若可用）。返回统计。

    :param tags: 自定义场景词表（None 则用内置 SCENE_CLIP_TAGS）
    """
    kw_added = _keyword_tags(db)
    clip_stats = auto_tag_clip(db, tags=tags)
    return {
        "added": kw_added + clip_stats.get("added", 0),
        "keyword_added": kw_added,
        "clip": clip_stats,
    }
