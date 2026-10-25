# -*- coding: utf-8 -*-
"""Chinese-CLIP 语义向量（离线 ONNX）：中文以文搜图 + 零样本场景标签。

模型来源：ModelScope `ondevice/cn-clip-onnx`（ViT-B/16 fp32，现成 ONNX 无需转换）
    models/clip/vit-b-16.img.fp32.onnx   图像编码器 -> [1,512]
    models/clip/vit-b-16.txt.fp32.onnx   文本编码器 -> [1,512]
    models/clip/vocab.txt                BERT 中文词表（21128）

踩过的坑（勿随意改动）：
- 输出名为 unnorm_*，**未做 L2 归一化**，必须手动归一化后才能算余弦相似度
- 文本输入是 int64 token，固定长度 52；[CLS]=101 [SEP]=102 [PAD]=0 [UNK]=100
- 图像预处理：resize 224x224(bicubic) -> /255 -> (x-mean)/std -> CHW
- 提示词模板实测「一张{}的照片」区分度最高（0.0285 -> 0.0365，+28%）
- cv2.imread 读不了中文路径，必须用 np.fromfile + imdecode
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

import cv2
import numpy as np

# 0.5.67：MODEL_ID 携带预处理版本（-cc1 = Resize+CenterCrop 对齐官方变换）。
# 旧向量（无 -cc1 后缀）与新 ID 不匹配 → 检索自动忽略、补跑机制按新 ID 重建。
MODEL_ID = "cn-clip-vit-b-16-cc1"
SUBDIR = "clip"
IMG_FILE = "vit-b-16.img.fp32.onnx"
TXT_FILE = "vit-b-16.txt.fp32.onnx"
VOCAB_FILE = "vocab.txt"

CLS, SEP, PAD, UNK = 101, 102, 0, 100
MAX_LEN = 52
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
QUERY_TEMPLATE = "一张{}的照片"


class ClipUnavailable(RuntimeError):
    """CLIP 模型文件缺失或无法加载。"""


def _l2(a: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(a, axis=-1, keepdims=True)
    return a / np.where(n == 0, 1.0, n)


def _wordpiece(word: str, vocab: dict[str, int]) -> list[str]:
    if word in vocab:
        return [word]
    out: list[str] = []
    start = 0
    while start < len(word):
        end, cur = len(word), None
        while start < end:
            sub = word[start:end]
            if start > 0:
                sub = "##" + sub
            if sub in vocab:
                cur = sub
                break
            end -= 1
        if cur is None:
            return ["[UNK]"]
        out.append(cur)
        start = end
    return out


def encode_tokens(text: str, vocab: dict[str, int], max_len: int = MAX_LEN) -> list[int]:
    """BERT 中文分词 -> token id 列表（含 CLS/SEP，补齐到 max_len）。"""
    ids = [CLS]
    for m in re.finditer(r"[\u4e00-\u9fff]|[a-z]+|[0-9]+", text.strip().lower()):
        w = m.group(0)
        if "\u4e00" <= w <= "\u9fff":
            ids.append(vocab.get(w, UNK))
        else:
            ids.extend(vocab.get(s, UNK) for s in _wordpiece(w, vocab))
    ids.append(SEP)
    if len(ids) > max_len:
        ids = ids[:max_len]
        ids[-1] = SEP
    ids += [PAD] * (max_len - len(ids))
    return ids


# 与 core/scanner.py 保持一致（此处独立定义以避免模块耦合）。
# 受支持的全部相机 RAW 格式清单（LibRaw/dcraw）。
RAW_EXTS = {
    ".3fr", ".ari", ".arw", ".bay", ".bmq", ".cap", ".cin", ".cr2", ".cr3",
    ".crw", ".dc2", ".dcr", ".dcs", ".dng", ".drf", ".eip", ".erf", ".fff",
    ".gpr", ".iiq", ".k25", ".kdc", ".mdc", ".mef", ".mos", ".mrw", ".nef",
    ".nrw", ".obm", ".orf", ".pef", ".ptx", ".pxn", ".qtk", ".raf", ".rwl",
    ".rw2", ".rwz", ".sr2", ".srf", ".srw", ".sti", ".x3f",
}


def prep_image(path: str | Path) -> np.ndarray:
    """读图并预处理为 [1,3,224,224] float32。

    cv2 无法解码 RAW（返回 None），RAW 必须走 rawpy；half_size 半尺寸解码足够 224 输入。

    0.5.67：预处理对齐 Chinese-CLIP 官方变换——此前直接拉伸 224×224，竖幅/横幅
    照片被压扁，图像向量与训练分布有偏移，语义匹配精度受损（用户反馈"不太准"）。
    现改为：短边缩放到 224（保持长宽比）+ 中心裁剪 224×224。预处理版本随
    MODEL_ID 升级（见 _PREP_VERSION），旧向量自动失效并由补跑机制重建。
    """
    path = str(path)
    if Path(path).suffix.lower() in RAW_EXTS:
        import rawpy
        with rawpy.imread(path) as raw:
            img = raw.postprocess(use_camera_wb=True, half_size=True)  # 输出 RGB
    else:
        buf = np.fromfile(path, dtype=np.uint8)
        bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError(f"无法读取图片: {path}")
        img = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    scale = 224.0 / min(h, w)
    img = cv2.resize(img, (max(1, round(w * scale)), max(1, round(h * scale))),
                     interpolation=cv2.INTER_CUBIC)
    h, w = img.shape[:2]
    top = max(0, (h - 224) // 2)
    left = max(0, (w - 224) // 2)
    img = img[top:top + 224, left:left + 224]
    if img.shape[0] != 224 or img.shape[1] != 224:
        # 极小图（短边不足 224 放大后仍不足）兜底：直接缩放
        img = cv2.resize(img, (224, 224), interpolation=cv2.INTER_CUBIC)
    x = img.astype(np.float32) / 255.0
    return np.ascontiguousarray(np.transpose((x - MEAN) / STD, (2, 0, 1))[None])


class ClipService:
    """CLIP 服务：延迟加载模型，未启用时不占内存。"""

    def __init__(self, models_dir: str | Path):
        self.dir = Path(models_dir) / SUBDIR
        self._img = None
        self._txt = None
        self._vocab: dict[str, int] | None = None
        self._lock = threading.Lock()

    # ---------- 可用性 ----------
    def missing_files(self) -> list[str]:
        return [f for f in (IMG_FILE, TXT_FILE, VOCAB_FILE)
                if not (self.dir / f).exists()]

    @property
    def available(self) -> bool:
        return not self.missing_files()

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._img is not None:
                return
            miss = self.missing_files()
            if miss:
                raise ClipUnavailable(
                    "缺少 Chinese-CLIP 模型文件：" + "、".join(miss) +
                    f"（应位于 {self.dir}）"
                )
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            self._img = ort.InferenceSession(
                str(self.dir / IMG_FILE), opts, providers=["CPUExecutionProvider"])
            self._txt = ort.InferenceSession(
                str(self.dir / TXT_FILE), opts, providers=["CPUExecutionProvider"])

    def _vocab_map(self) -> dict[str, int]:
        if self._vocab is None:
            v: dict[str, int] = {}
            with open(self.dir / VOCAB_FILE, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    v[line.rstrip("\n")] = i
            self._vocab = v
        return self._vocab

    # ---------- 编码 ----------
    def encode_text(self, query: str, template: bool = True) -> np.ndarray:
        """中文查询 -> 512 维单位向量。"""
        self._ensure_loaded()
        q = QUERY_TEMPLATE.format(query) if template else query
        ids = np.array([encode_tokens(q, self._vocab_map())], dtype=np.int64)
        return _l2(self._txt.run(None, {"text": ids})[0])[0]

    def encode_image(self, path: str | Path) -> np.ndarray:
        """图片 -> 512 维单位向量。"""
        self._ensure_loaded()
        return _l2(self._img.run(None, {"image": prep_image(path)})[0])[0]


def encode_indexable(svc: "ClipService", db_path: str, file_path: str,
                     thumb_path=None, tw=None, th=None,
                     frames=None) -> np.ndarray | None:
    """clip-index 单条编码（0.5.51：照片 + 视频关键帧统一入口）。

    - 视频（frames 非空）：各关键帧分别编码后取平均，再 L2 归一
      → 一个向量代表整段视频内容，使其进入「clip:文字」语义搜索与场景标签；
    - 照片：优先 ≥256px 的缩略图（解码快），否则原图；
    - 文件缺失/编码失败 → None（调用方计 fail）。
    返回单位向量或 None。
    """
    import numpy as np  # noqa: PLC0415

    if frames:
        vecs = []
        for fp in frames:
            from pathlib import Path as _P

            from photo_manager.core.paths import resolve_data_path

            ap = resolve_data_path(db_path, fp)
            if not _P(ap).exists():
                continue
            try:
                vecs.append(svc.encode_image(ap))
            except Exception:
                continue
        if not vecs:
            return None
        v = np.mean(vecs, axis=0)
        n = float(np.linalg.norm(v))
        return (v / n).astype(np.float32) if n > 1e-9 else None
    src = file_path
    if thumb_path:
        try:
            from pathlib import Path as _P

            from photo_manager.core.paths import resolve_data_path

            at = resolve_data_path(db_path, thumb_path)
            if max(tw or 0, th or 0) >= 256 and _P(at).exists():
                src = at
        except Exception:
            pass
    from pathlib import Path as _P  # noqa: PLC0415

    if not _P(src).exists():
        return None
    try:
        return svc.encode_image(src)
    except Exception:
        return None


def cli_worker_main(argv) -> int:
    """--clip-worker 子进程入口（0.5.58）。

    argv: [exe, --clip-worker, db_path, jobs_json, out_json, mode]
    mode: "encode"（jobs=编码批）| "autotag"（jobs=tags 列表）
    编码/打标在无 Qt 的独立进程中完成——Qt 6.11 环境下后台线程首次加载/运行
    native 重库（rawpy/onnxruntime/libraw）会访问违例（0.5.57 用户实测）。
    结果 JSON 写 out_json：{"ok": int, "fail": int, "tags": int}。
    """
    import json
    import sqlite3

    db_path, jobs_json, out_json, mode = argv[2], argv[3], argv[4], argv[5]
    result = {"ok": 0, "fail": 0, "tags": 0, "vectors": []}
    try:
        with open(jobs_json, encoding="utf-8") as f:
            payload = json.load(f)
        if mode == "autotag":
            import sqlite3

            from photo_manager.core import autotag

            conn = sqlite3.connect(db_path, timeout=30)
            try:
                svc = get_service()
                st = autotag.auto_tag_clip(conn, svc=svc, tags=payload)
                result["tags"] = int(st.get("added", 0))
            finally:
                conn.close()
        else:
            # 0.5.58：子进程不写库（向量 base64 回传主进程写）——
            # 隔离"子进程写库 + 主进程 sqlite mmap 并发"的崩溃源
            import base64

            svc = get_service()
            for pid, fp, tp, tw, th, frames in payload:
                vec = encode_indexable(svc, db_path, fp, tp, tw, th, frames)
                if vec is None:
                    result["fail"] += 1
                    continue
                b64 = base64.b64encode(
                    vec.astype(np.float32).tobytes()).decode("ascii")
                result["vectors"].append([pid, b64, MODEL_ID, int(vec.shape[0])])
                result["ok"] += 1
    except Exception:
        import traceback

        result["error"] = traceback.format_exc()
        rc = 1
    else:
        rc = 0
    finally:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
    return rc


_service: ClipService | None = None
_svc_lock = threading.Lock()


def get_service(models_dir: str | None = None) -> ClipService:
    """获取进程内共享的 CLIP 服务（延迟创建模型目录句柄，不加载模型）。"""
    global _service
    with _svc_lock:
        if _service is None:
            if models_dir is None:
                from photo_manager import models_dir as _md
                models_dir = _md()
            _service = ClipService(models_dir)
        return _service


# ---------- 以图搜图（相似照片） ----------
def find_similar(db, photo_id: int, topk: int = 120) -> list[tuple[int, float]]:
    """以图搜图：给定照片，按 CLIP 图像向量余弦相似度返回最相似的 topk 张。

    - 优先复用 photo_embeddings 中已存向量（无编码开销）；
      该照片尚无向量时，现场用缩略图/原图编码一次（模型缺失返回空）。
    - 排除自身、missing 与已归档照片；不修改任何数据（纯只读）。
    - 返回 [(photo_id, score)]，相似度降序。
    """
    import numpy as np

    try:
        row = db.conn.execute(
            "SELECT embedding FROM photo_embeddings WHERE photo_id=? AND model=?",
            (photo_id, MODEL_ID),
        ).fetchone()
    except Exception:
        return []
    if row:
        qv = np.frombuffer(row[0], dtype=np.float32)
    else:
        # 查询照片无向量：现场编码（缩略图优先）
        try:
            svc = get_service()
            if not svc.available:
                return []
            src = db.conn.execute(
                "SELECT file_path, thumbnail_path, thumb_width, thumb_height"
                " FROM photos WHERE id=?", (photo_id,),
            ).fetchone()
            if not src:
                return []
            path = src[1] if (src[1] and max(src[2] or 0, src[3] or 0) >= 256) else src[0]
            qv = svc.encode_image(path)
        except Exception:
            return []
    n = np.linalg.norm(qv)
    if n == 0:
        return []
    qv = qv / n

    scored: list[tuple[float, int]] = []
    chunk, last = 5000, 0
    while True:
        rows = db.conn.execute(
            "SELECT e.photo_id, e.embedding FROM photo_embeddings e"
            " JOIN photos p ON p.id = e.photo_id"
            " WHERE e.model = ? AND e.photo_id > ? AND e.photo_id != ?"
            " AND p.status != 'missing' AND p.archived = 0"
            " ORDER BY e.photo_id LIMIT ?",
            (MODEL_ID, last, photo_id, chunk),
        ).fetchall()
        if not rows:
            break
        last = rows[-1][0]
        mat = np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
        # 库内向量历史版本可能未归一化，保险起见逐行归一化后算余弦
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        mat = mat / np.where(norms == 0, 1.0, norms)
        sims = mat @ qv
        scored.extend(zip(sims.tolist(), [r[0] for r in rows]))
    scored.sort(key=lambda x: -x[0])
    return [(pid, round(float(s), 4)) for s, pid in scored[:topk]]
