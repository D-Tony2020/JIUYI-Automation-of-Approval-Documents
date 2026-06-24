# -*- coding: utf-8 -*-
"""W4 材质成分展开表：表头 + 变行数据区(LLM JOIN) + 浮动底部 RoHS 排除表。

- 抽取(mock/live) → assemble_row(归一, 含 weight 单位嗅探修复) → 嵌套合并注入(复用 m7 结构)。
- 底部 RoHS 排除表 = 固定静态块，从模板捕获后浮动摆放到数据区之后(签认: 浮动)。
- J2 填表日期: 清模板硬编码的 2026-06-18, 填生成日。
"""
import os
import re
import json
import datetime
from openpyxl.styles import Border, Side, Alignment, Font

# 成份名称标准词表(由7样本实证归纳): {材质: {cas: 标准名}}。查不到→保留MSDS原文。
_DICT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "成份名称词表.json")
try:
    with open(_DICT_PATH, encoding="utf-8") as _f:
        _COMP_DICT = json.load(_f)
except Exception:
    _COMP_DICT = {}


def normalize_component_name(材质, cas, raw):
    """按 (材质,CAS) 查标准词表归一成份名；查不到则保留 MSDS 原文(交人工)。"""
    std = _COMP_DICT.get((材质 or "").strip(), {}).get((cas or "").strip())
    return std if std else (raw or "").strip()

MAT_SHEET = "7.材质成分展开表 "

THIN = Side(style="thin", color="000000")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
FONT = Font(name="宋体", size=9)

ROHS_KEYS = ["Pb", "Cd", "Hg", "Cr6+", "PBBs", "PBDEs", "DEHP", "DBP", "BBP", "DIBP"]
ROHS_COL = {k: 13 + i for i, k in enumerate(ROHS_KEYS)}   # M..V
PART_MERGE_COLS = [1, 2, 3]                # A,B,C 跨整个零件
MAT_MERGE_COLS = [4, 5, 6]                 # D材质类别,E材质,F材质重量 跨整个材质
BLOCK_MERGE_COLS = [11, 12] + list(range(13, 31))  # K,L,M..AD 跨同一报告块(支持多色)
DATA_TOP = 14

SUPPLIER_ALIAS = {
    "兴鸿泰": ["兴鸿泰", "興鴻泰", "兴鸿泰锡业", "興鴻泰錫業", "深圳市兴鸿泰锡业有限公司", "XING HONG TAI"],
}
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")


def _fmt(v):
    return ("%f" % v).rstrip("0").rstrip(".")


def normalize_cas(raw):
    if not raw:
        return ""
    s = re.sub(r"\s+", "", str(raw))
    return s if _CAS_RE.match(s) else str(raw).strip()


def normalize_supplier(raw):
    raw = (raw or "").strip()
    for canon, aliases in SUPPLIER_ALIAS.items():
        if any(a.lower() in raw.lower() for a in aliases):
            return canon
    return raw


def normalize_weight(raw):
    """单位嗅探(签认): 带%或>1→÷100; ≤1且无%→已是小数不除; <3/>x/余量 原样。"""
    if raw is None:
        return ""
    s = str(raw).strip()
    if "余量" in s or s.lower() in ("balance", "bal"):
        return "余量"
    if s and s[0] in "<≤>":
        return s.replace(" ", "")
    has_pct = "%" in s
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if not m:
        return s
    val = float(m.group(0))
    if has_pct or val > 1:
        return _fmt(val / 100.0)
    return _fmt(val)   # ≤1 且无% → 已是小数, 不再除(needs_review 另行 track)


def normalize_date(raw):
    if not raw:
        return ""
    s = str(raw).strip()
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}.{int(m.group(2)):02d}.{int(m.group(3)):02d}"
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        if mon:
            return f"{m.group(3)}.{mon:02d}.{int(m.group(2)):02d}"
    return s


def normalize_rohs(result):
    s = str(result).strip()
    if s.upper().replace(".", "") == "ND":
        return "ND"
    m = re.search(r"[-+]?\d*\.?\d+", s)
    return m.group(0) if m else s


def assemble_row(msds, rohs, 零件, 材质类别, 材质):
    """MSDS 抽取 ⋈ RoHS 抽取 → 材质表一行(归一后)。"""
    成份 = []
    for c in msds.get("components", []):
        cas = normalize_cas(c.get("cas", ""))
        成份.append({
            "成份名称": normalize_component_name(材质, cas, c.get("name", "")),
            "CAS": cas,
            "重量%": normalize_weight(c.get("weight_pct_raw", "")),
        })
    rin = rohs.get("rohs", {})
    rout = {}
    for k in ROHS_KEYS:
        cell = rin.get(k, {})
        rout[k] = normalize_rohs(cell.get("result", "")) if isinstance(cell, dict) else normalize_rohs(cell)
    return {"零件": 零件, "材质类别": 材质类别, "材质": 材质,
            "供应商": normalize_supplier(msds.get("supplier_name_raw", "")),
            "成份": 成份, "RoHS": rout,
            "检测报告编号": (rohs.get("report_number", "") or "").strip(),
            "检测报告日期": normalize_date(rohs.get("report_date_raw", ""))}


def _style(ws, r, c, align=CENTER):
    cell = ws.cell(r, c)
    cell.border = BORDER
    cell.alignment = align
    cell.font = FONT


def _capture_bottom_block(ws):
    """清区前捕获底部 RoHS 排除表(标题行起到表尾)，返回 [(A值, B值)]。避免重打 22 行。"""
    start = None
    for r in range(40, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v and "RoHS排除管制对象" in str(v):
            start = r
            break
    if start is None:
        return []
    block = [(ws.cell(r, 1).value, ws.cell(r, 2).value) for r in range(start, ws.max_row + 1)]
    while block and block[-1][0] is None and block[-1][1] is None:
        block.pop()
    return block


def _clear_region(ws, top, bottom):
    for mr in list(ws.merged_cells.ranges):
        min_c, min_r, max_c, max_r = mr.bounds
        if min_r >= top and max_r <= bottom:
            ws.unmerge_cells(str(mr))
    for row in ws.iter_rows(min_row=top, max_row=bottom, min_col=1, max_col=30):
        for cell in row:
            cell.value = None


def inject_data(ws, bom, start_row=DATA_TOP):
    """三层嵌套合并注入：零件(A/B/C) → 材质(D/E/F) → 报告块(K/L/M-V/W/X/AB/AC…)。

    报告块支持多色：一材质可含多份报告，每份盖住自己的成份子组(如 PVC 黑+红)。返回数据末行。
    """
    r = start_row
    for idx, part in enumerate(bom, 1):
        ps = r
        for mat in part["materials"]:
            ms = r
            for block in mat["blocks"]:
                bs = r
                for comp in block["成份"]:
                    ws.cell(r, 7, comp.get("成份名称", ""))
                    ws.cell(r, 8, comp.get("CAS", ""))
                    ws.cell(r, 10, comp.get("重量%", ""))
                    r += 1
                be = r - 1
                # 报告块级：RoHS十项 + 报告号/日期 + 合规占位
                for k in ROHS_KEYS:
                    ws.cell(bs, ROHS_COL[k], block.get("RoHS", {}).get(k, ""))
                ws.cell(bs, 23, block.get("报告日期", ""))
                ws.cell(bs, 24, block.get("报告编号", ""))
                ws.cell(bs, 9, "/")       # I weight(g)
                ws.cell(bs, 26, "/")      # Z Br
                ws.cell(bs, 27, "/")      # AA Cl
                ws.cell(bs, 28, "Yes")    # AB 是否符合
                ws.cell(bs, 29, "否")      # AC 是否RoHS排外
                ws.cell(bs, 30, "/")      # AD 排除项次
                if be > bs:
                    for c in BLOCK_MERGE_COLS:
                        ws.merge_cells(start_row=bs, start_column=c, end_row=be, end_column=c)
            me = r - 1
            # 材质级：材质类别/材质/材质重量
            ws.cell(ms, 4, mat.get("材质类别", ""))
            ws.cell(ms, 5, mat.get("材质", ""))
            ws.cell(ms, 6, "/")       # F 材质重量 占位
            if me > ms:
                for c in MAT_MERGE_COLS:
                    ws.merge_cells(start_row=ms, start_column=c, end_row=me, end_column=c)
        pe = r - 1
        # 零件级：项次/零件/供应商
        ws.cell(ps, 1, idx)
        ws.cell(ps, 2, part.get("零件", ""))
        ws.cell(ps, 3, part.get("供应商", ""))
        if pe > ps:
            for c in PART_MERGE_COLS:
                ws.merge_cells(start_row=ps, start_column=c, end_row=pe, end_column=c)
        for rr in range(ps, pe + 1):
            for cc in range(1, 31):
                _style(ws, rr, cc)
    return r - 1


def place_bottom_block(ws, block, start_row):
    """把捕获的底部排除表浮动摆到 start_row(B:M 合并)。"""
    for i, (a, b) in enumerate(block):
        r = start_row + i
        ws.cell(r, 1, a)
        ws.cell(r, 2, b)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=13)
        _style(ws, r, 1, CENTER)
        _style(ws, r, 2, LEFT)
    return start_row + len(block) - 1


def fill_material_table(ws, bom, product, gap=2):
    """表头 + 数据区 + 浮动底部表。返回 (数据末行, 底部表起始行)。"""
    block = _capture_bottom_block(ws)
    _clear_region(ws, DATA_TOP, ws.max_row)
    # 表头
    ws["A2"] = f"供货商类别  :{product['材料名称']}"
    today = product.get("填表日期") or datetime.date.today()
    if isinstance(today, datetime.date):
        ws["J2"] = f"填表日期 :                 {today.year} 年   {today.month:02d}   月  {today.day:02d}   日"
    else:
        ws["J2"] = f"填表日期 :                 {today}"
    # 数据区
    last = inject_data(ws, bom, DATA_TOP)
    # 浮动底部表
    bottom_start = last + 1 + gap
    if block:
        place_bottom_block(ws, block, bottom_start)
    return last, bottom_start


def selfcheck_material(ws, checks):
    """读回断言关键格。checks={coord: expected}。返回错误列表。"""
    errs = []
    for coord, exp in checks.items():
        got = ws[coord].value
        if str(got) != str(exp):
            errs.append(f"{coord}: 期望 {exp!r}，实得 {got!r}")
    return errs
