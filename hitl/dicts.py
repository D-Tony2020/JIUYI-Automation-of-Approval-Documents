# -*- coding: utf-8 -*-
"""全局字典层(跨客户共用, 持久化): 材质简称 + 材质→类别→零件反查 + 供应商历史。

材质为锚: 操作员改材质名 → 标准名(简称字典, 规范化包含匹配) → 材质类别/零件(反查字典)。
未知材质 → 操作员设类别/零件 → learn_* 回写学习(下次同料自动出)。
仿 material_table 的 成份名称词表.json 模式; 文件在 hitl/data/。
"""
import json
import os
import re

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_FILES = {"alias": "材质简称字典.json", "catpart": "材质类别零件字典.json", "supplier": "供应商历史.json"}


def _path(kind):
    return os.path.join(DATA, _FILES[kind])


def _load(kind, default):
    try:
        with open(_path(kind), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(kind, data):
    os.makedirs(DATA, exist_ok=True)
    with open(_path(kind), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _norm(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


def alias_table():
    return _load("alias", {})            # {标准名: [token变体]}


def catpart_table():
    return _load("catpart", {})          # {标准材质名: {材质类别, 零件}}


def supplier_history():
    return _load("supplier", [])


def std_name(原文, alias=None):
    """原文材质名 → 标准名(规范化后包含匹配, 命中 token 最长者胜)。无命中→原文 strip。"""
    alias = alias_table() if alias is None else alias
    h = _norm(原文)
    best, blen = None, 0
    for std, toks in alias.items():
        for t in toks:
            tn = _norm(t)
            if tn and tn in h and len(tn) > blen:
                best, blen = std, len(tn)
    return best or str(原文 or "").strip()


def resolve_material(原文, alias=None, catpart=None):
    """原文 → {标准名, 材质类别, 零件}。反查 1:1; 未知类别/零件留空(交人工→learn 回写)。"""
    alias = alias_table() if alias is None else alias
    catpart = catpart_table() if catpart is None else catpart
    std = std_name(原文, alias)
    info = catpart.get(std, {}) or {}
    return {"标准名": std, "材质类别": info.get("材质类别", ""), "零件": info.get("零件", "")}


def learn_alias(原文, std):
    """记忆: 原文(strip)作为 std 的一个 token(去重)。下次同原文自动出该标准名。"""
    raw = str(原文 or "").strip()
    std = str(std or "").strip()
    if not raw or not std:
        return alias_table()
    t = alias_table()
    toks = t.setdefault(std, [])
    if raw not in toks:
        toks.append(raw)
    _save("alias", t)
    return t


def learn_catpart(std, 材质类别, 零件):
    """记忆: 标准材质名 → {类别, 零件}。下次同材质自动派生。"""
    std = str(std or "").strip()
    if not std:
        return catpart_table()
    t = catpart_table()
    t[std] = {"材质类别": str(材质类别 or "").strip(), "零件": str(零件 or "").strip()}
    _save("catpart", t)
    return t


def add_supplier(name):
    """供应商历史去重追加(零件级下拉用)。"""
    name = str(name or "").strip()
    if not name:
        return supplier_history()
    h = supplier_history()
    if name not in h:
        h.append(name)
        _save("supplier", h)
    return h


def all_dicts():
    """前端一次拉全(BOM 页 resolve + 下拉)。"""
    return {"alias": alias_table(), "catpart": catpart_table(), "suppliers": supplier_history()}
