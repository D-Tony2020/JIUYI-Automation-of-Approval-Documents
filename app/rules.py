# -*- coding: utf-8 -*-
"""后端权威规则校验(与前端 app/web/js/rules.js 同规则)。

前端放行门可被绕过(直接打 API), 后端 confirm 必须独立权威校验——放行前提是
"操作员逐条声明照图核对过", 后端兜底确认空槽/格式/勾核齐备才落档。
"""
import re

_LABELS = ["品号", "版本", "名称"]
_KEYS = ["id0", "id1", "id2"]


def check_version(v):
    return bool(re.fullmatch(r"[A-Za-z]\d{2}", str(v or "").strip()))   # A01/B02


def check_code(v):
    s = str(v or "").strip()
    return len(s) >= 6 and bool(re.search(r"[A-Za-z]", s)) and bool(re.search(r"\d", s))


def check_name(v):
    return len(str(v or "").strip()) > 0


def check_dim(dim):
    try:
        c = float(dim.get("中心"))
        up = float(dim.get("上"))
        lo = float(dim.get("下", up))
    except (TypeError, ValueError, AttributeError):
        return False
    return up >= 0 and lo >= 0                                          # 公差非负


def validate_confirm(body):
    """返回缺项列表(空=可放行)。三要素 格式+勾核; 尺寸 格式+(勾核 或 豁免)。"""
    missing = []
    checked = body.get("checked") or {}
    for label, key, ok in zip(_LABELS, _KEYS,
                              [check_code(body.get("品号")), check_version(body.get("版本")), check_name(body.get("名称"))]):
        if not ok:
            missing.append(label + "格式异常")
        if not checked.get(key):
            missing.append(label + "未勾核")
    exempt = {e.get("序号") for e in (body.get("exemptions") or [])}
    for i, dim in enumerate(body.get("dimensions") or []):
        if i in exempt:
            continue
        if not check_dim(dim):
            missing.append(f"尺寸{i + 1}公差异常")
        if not checked.get("dim" + str(i)):
            missing.append(f"尺寸{i + 1}未勾核")
    return missing
