# -*- coding: utf-8 -*-
"""装配层（确定性代码）：MSDS 抽取 ⋈ RoHS 抽取 → 材质表一行。

承载已确认的填写规则：
- 重量%：wt%/百分数 → 小数；'<3'、'余量/balance' 原样保留；不强制凑 100%。
- RoHS：'N.D.'/'ND' 归一为 'ND'；具体数值照填（mg/kg=ppm，去单位）。
- 日期：英文/各种写法 → YYYY.MM.DD。
- 供应商名：繁体/简体/英文 → 别名归一到久益惯用简称。
"""
import re

from schemas import ROHS_KEYS

# 供应商别名表（实际产品里维护成主数据）
SUPPLIER_ALIAS = {
    "兴鸿泰": ["兴鸿泰", "興鴻泰", "兴鸿泰锡业", "興鴻泰錫業", "深圳市兴鸿泰锡业有限公司",
              "SHENZHEN XING HONG TAI TIN", "XING HONG TAI"],
}

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")


def normalize_cas(raw: str) -> str:
    """修复窄列抽取产生的 CAS 空格（'7440-31- 5' / '65997-05 -9' → '7440-31-5'）。"""
    if not raw:
        return ""
    s = re.sub(r"\s+", "", str(raw))
    return s if _CAS_RE.match(s) else str(raw).strip()


def normalize_supplier(raw: str) -> str:
    raw = (raw or "").strip()
    for canon, aliases in SUPPLIER_ALIAS.items():
        if any(a.lower() in raw.lower() for a in aliases):
            return canon
    return raw  # 未命中则原样返回，交人工复核


def normalize_weight(raw: str) -> str:
    """99.3wt% / 99.3% / 99.3 → 0.993；'<3'、'余量' 原样。"""
    if raw is None:
        return ""
    s = str(raw).strip()
    if "余量" in s or s.lower() in ("balance", "bal"):
        return "余量"
    if s.startswith("<") or s.startswith("≤"):
        return s.replace(" ", "")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if not m:
        return s
    # MSDS 成分列恒为百分数(wt%)，一律 ÷100 化为小数(与承认书口径一致)
    val = float(m.group(0)) / 100.0
    # 去掉浮点尾巴
    return ("%f" % val).rstrip("0").rstrip(".")


def normalize_date(raw: str) -> str:
    """Jun 30, 2025 / 2025.06.30 / 2025-06-30 → 2025.06.30。"""
    if not raw:
        return ""
    s = raw.strip()
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}.{int(m.group(2)):02d}.{int(m.group(3)):02d}"
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        if mon:
            return f"{m.group(3)}.{mon:02d}.{int(m.group(2)):02d}"
    return s


def normalize_rohs(result: str) -> str:
    """'N.D.'/'nd' → 'ND'；具体数值去单位照填。"""
    s = str(result).strip()
    if s.upper().replace(".", "") == "ND":
        return "ND"
    m = re.search(r"[-+]?\d*\.?\d+", s)
    return m.group(0) if m else s


def assemble_row(msds: dict, rohs: dict, 零件: str, 材质类别: str, 材质: str) -> dict:
    成份 = [{
        "成份名称": c.get("name", ""),
        "CAS": normalize_cas(c.get("cas", "")),
        "重量%": normalize_weight(c.get("weight_pct_raw", "")),
    } for c in msds.get("components", [])]

    rohs_in = rohs.get("rohs", {})
    rohs_out = {}
    for k in ROHS_KEYS:
        cell = rohs_in.get(k, {})
        rohs_out[k] = normalize_rohs(cell.get("result", "")) if isinstance(cell, dict) else normalize_rohs(cell)

    return {
        "零件": 零件,
        "材质类别": 材质类别,
        "材质": 材质,
        "原材料供应商": normalize_supplier(msds.get("supplier_name_raw", "")),
        "成份": 成份,
        "RoHS": rohs_out,
        "检测报告编号": rohs.get("report_number", "").strip(),
        "检测报告日期": normalize_date(rohs.get("report_date_raw", "")),
    }
