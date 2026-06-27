# -*- coding: utf-8 -*-
"""全局字典层(跨客户共用, 持久化): 材质简称 + 材质→类别→零件反查 + 供应商历史。

材质为锚: 操作员改材质名 → 标准名(简称字典, 规范化包含匹配) → 材质类别/零件(反查字典)。
未知材质 → 操作员设类别/零件 → learn_* 回写学习(下次同料自动出)。
仿 material_table 的 成份名称词表.json 模式; 文件在 hitl/data/。
"""
import json
import os
import re
import shutil

from hitl import userdata

# 字典学习库跟用户走(%APPDATA%, 重装/升级继承); 种子随程序(hitl/data, 首启播种)。
DATA = os.path.join(userdata.USER_DATA_DIR, "dicts")
_SEED = os.path.join(userdata.resource_base(), "hitl", "data")
_FILES = {"alias": "材质简称字典.json", "catpart": "材质类别零件字典.json",
          "supplier": "供应商历史.json", "part_order": "零件顺序.json",
          "assign": "归属学习.json",                  # 报告归属在线学习(成长型)
          "category": "品类词字典.json"}              # 封面D12品类词学习(成长型: 名称→品类)


def ensure_seeded():
    """首启: %APPDATA% 无字典则从随程序的种子拷一份(新机有合理默认); 已存在不覆盖(保用户积累)。"""
    try:
        os.makedirs(DATA, exist_ok=True)
    except OSError:
        return
    for fn in _FILES.values():
        dst, seed = os.path.join(DATA, fn), os.path.join(_SEED, fn)
        if not os.path.exists(dst) and os.path.exists(seed):
            try:
                shutil.copyfile(seed, dst)
            except OSError:
                pass


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
    p = _path(kind)
    tmp = p + ".tmp"                              # 原子写(临时文件+替换), 防写一半坏档
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


ensure_seeded()                                  # import 即播种(幂等); 单测覆盖 DATA 后不受影响


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


def _learn_keys(filename):
    """报告文件名→可泛化稳定关键词(型号码/类型词/供应商); 去日期与长流水号(否则每单唯一不可学)。"""
    base = os.path.splitext(os.path.basename(str(filename or "")))[0]
    base = re.sub(r"20\d{2}[.\-/年]?\d{0,2}[.\-/月]?\d{0,2}", " ", base)   # 去日期
    base = re.sub(r"\d{6,}", " ", base)                                     # 去长流水号(CANEC26012090003)
    keys = set()
    for m in re.findall(r"[A-Za-z]{1,}-?\d+[A-Za-z0-9\-]*", base):          # 字母型号码 XH-T21 / A2501
        if 2 <= len(m) <= 14:
            keys.add(m.upper())
    for m in re.findall(r"(?<![A-Za-z\d])\d{3,5}(?![A-Za-z\d])", base):     # 纯数字型号码 1061(已去日期/长流水号)
        keys.add(m)
    for w in ("盐雾", "高温", "老化", "信赖", "热缩", "套管", "镀锡", "端子", "胶座", "白色", "黑色",
              "油墨", "CANEC", "SHAEC", "SZXEC", "正崴", "联和", "领飞", "双鸿"):
        if w in base or w.lower() in base.lower():
            keys.add(w)
    return keys


# 归位目标受控枚举(成长学习第三维): 材质证据列 / 横排·页级槽 / 排除。非此集的 目标 一律丢弃。
ASSIGN_TARGETS = {"col:K", "col:L", "col:Y",
                  "slot:部件承认", "slot:UL", "slot:信赖性", "slot:包装", "slot:出货", "slot:图纸",
                  "exclude"}
_SUPPLIER_HINT = ("正崴", "联和", "领飞", "双鸿", "永超", "三博", "奥升德", "立讯", "得意")


def _strong_key(filename):
    """文件名是否含强键(供应商名 / 字母型号码 / ≥4位纯数字料号): 无监督强自动落位的门槛——
    纯业务词键(端子/盐雾)易跨单串味, 只准弱建议; 强键才允许自动落位。"""
    base = os.path.splitext(os.path.basename(str(filename or "")))[0]
    if any(s in base for s in _SUPPLIER_HINT):
        return True
    b = re.sub(r"20\d{2}[.\-/年]?\d{0,2}[.\-/月]?\d{0,2}", " ", base)   # 去日期
    b = re.sub(r"\d{6,}", " ", b)                                        # 去长流水号(同 _learn_keys)
    return bool(re.search(r"[A-Za-z]{1,}-?\d{2,}", b)                    # 字母型号码 C2001/A2501
                or re.search(r"(?<![A-Za-z\d])\d{4,5}(?![A-Za-z\d])", b))  # ≥4位纯数字料号


def learn_assign(filename, 材质=None, 零件=None, 目标=None):
    """学习报告归属(操作员④确认的=真值, 成长型): 文件名关键词→材质/零件/目标 投票计数。
    目标∈ASSIGN_TARGETS(归到材质列K/L/Y · 横排/页级槽 · 排除); 见 [[jiuyi-hitl-knowledge-must-persist]]。"""
    keys = _learn_keys(filename)
    目标 = 目标 if 目标 in ASSIGN_TARGETS else None
    if not keys or not ((材质 or "").strip() or (零件 or "").strip() or 目标):
        return
    t = _load("assign", {})
    for k in keys:
        slot = t.setdefault(k, {"材质": {}, "零件": {}, "目标": {}})
        slot.setdefault("目标", {})                  # 旧档(无目标键)补维, 不破
        for fld, v in (("材质", (材质 or "").strip()), ("零件", (零件 or "").strip()), ("目标", 目标 or "")):
            if v:
                slot[fld][v] = slot[fld].get(v, 0) + 1
    _save("assign", t)


def lookup_assign(filename):
    """查学习字典: 文件名关键词→票数最高的 材质/零件/目标(+目标票, 跨关键词累加投票)。无→{}。"""
    keys = _learn_keys(filename)
    if not keys:
        return {}
    t = _load("assign", {})
    agg = {"材质": {}, "零件": {}, "目标": {}}
    for k in keys:
        slot = t.get(k) or {}
        for fld in ("材质", "零件", "目标"):
            for v, c in (slot.get(fld) or {}).items():    # 旧档无'目标'键→.get 返回空, 兼容
                agg[fld][v] = agg[fld].get(v, 0) + c
    out = {}
    for fld in ("材质", "零件", "目标"):
        if agg[fld]:
            best, votes = max(agg[fld].items(), key=lambda kv: kv[1])
            out[fld] = best
            if fld == "目标":
                out["目标票"] = votes
    return out


def assign_table():
    return _load("assign", {})            # {关键词: {材质:{名:票}, 零件:{名:票}, 目标:{枚举:票}}}


def forget_assign(key=None, 维度=None, 值=None):
    """清理归属学习(可见可清理红线): 删整条 key / 某维度 / 某维度某项。返回更新后的表。"""
    t = _load("assign", {})
    if key is None or key not in t:
        return t
    if 维度 and 值 and 维度 in t[key]:
        t[key][维度].pop(值, None)
    elif 维度 and 维度 in t[key]:
        t[key][维度] = {}
    else:
        t.pop(key, None)
    _save("assign", t)
    return t


def category_dict():
    return _load("category", {})         # {规范化完整名称: 品类词}


_PAREN_STRIP = re.compile(r"[（(\[【][^（()）\[\]【】]*[)）\]】]")


def learn_category(名称, 品类):
    """记忆: 完整图纸名称(规范化)→品类词(操作员④确认的=真值, 成长型)。
    完整名精确 key 防跨单串味; 下次同名(及去括号色变体)自动命中。"""
    key = _norm(名称)
    品类 = str(品类 or "").strip()
    if not key or not 品类:
        return category_dict()
    t = category_dict()
    t[key] = 品类
    _save("category", t)
    return t


def lookup_category(名称):
    """查品类词学习库: 先完整名精确; 再'去括号修饰后相等'弱回退(导线(黄)学过→导线(红)命中)。无→''。"""
    key = _norm(名称)
    if not key:
        return ""
    t = category_dict()
    if key in t:
        return t[key]
    bare = _PAREN_STRIP.sub("", key).strip()
    if bare:
        for k, v in t.items():
            if _PAREN_STRIP.sub("", k).strip() == bare:
                return v
    return ""


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


def part_order():
    """零件展示/项次顺序(全局持久化; 业务上改一次基本固定)。"""
    return _load("part_order", [])


def set_part_order(order):
    """拖动排序后落盘(去空/去重保序)。"""
    seen, out = set(), []
    for p in order or []:
        p = str(p or "").strip()
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    _save("part_order", out)
    return out


def order_parts(parts, order=None):
    """把零件列表按持久化顺序排(顺序内的按序在前, 顺序外的按原序追加)。"""
    order = part_order() if order is None else order
    idx = {p: i for i, p in enumerate(order)}
    return sorted(parts, key=lambda p: (idx.get(p, len(order)),))


def all_dicts():
    """前端一次拉全(BOM 页 resolve + 下拉 + 零件顺序)。"""
    return {"alias": alias_table(), "catpart": catpart_table(),
            "suppliers": supplier_history(), "part_order": part_order(),
            "assign": assign_table()}                 # 归属学习(可见可清理)
