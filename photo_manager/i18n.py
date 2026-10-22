# -*- coding: utf-8 -*-
"""Python 侧多语言支持（0.5.66）。

与 QML 侧共用同一份语言包（ui/qml/i18n/<code>.json，键为中文源串）。
新增语言：放入新 <code>.json 并在 I18n.qml 的 availableLanguages 登记——
无需改动任何代码。缺词回退中文原文。
"""
from __future__ import annotations

import json
from pathlib import Path

_CATALOG_DIR = Path(__file__).resolve().parent / "ui" / "qml" / "i18n"

_lang = "zh"
_catalogs: dict[str, dict[str, str]] = {}


def get_lang() -> str:
    return _lang


def set_lang(code: str) -> None:
    """切换语言（QSettings 由 bridge 写入，此处只同步内存态）。"""
    global _lang
    _lang = code if code else "zh"


def _catalog(code: str) -> dict[str, str]:
    if code not in _catalogs:
        p = _CATALOG_DIR / f"{code}.json"
        if p.exists():
            try:
                _catalogs[code] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — 语言包损坏时回退中文
                _catalogs[code] = {}
        else:
            _catalogs[code] = {}
    return _catalogs[code]


def t(s: str) -> str:
    """翻译 UI 字符串；缺词回退中文原文。"""
    if _lang == "zh" or not s:
        return s
    v = _catalog(_lang).get(s.strip())
    return s if v is None else v
