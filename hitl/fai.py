# -*- coding: utf-8 -*-
"""W5 FAI 全尺寸：治病清旧值 + 表头 + 图纸尺寸→规格上下限 + 32组实测红槽。

- E-H(Mean/Stdev/CP/CPK)是模板自带公式，保留不碰，实测填后自动算。
- 规格 B/C/D 由图纸尺寸 n±t 算：B=n−t, C=n, D=n+t。项数=图纸尺寸数。
- 32组实测(I-AN)=人工红槽。表头 I2/O2 公式联动封面；C2品类/U2生成日 由工具填；签名静态。
"""
import datetime

from .harness import highlight_cell

FAI_SHEET = "5.供应商测试报告(FAI)"
ITEM_ROW0 = 9            # 首个 item 行
ITEM_ROWN = 38           # 模板 item 1-30 (行9-38)
SPEC_COLS = [2, 3, 4]    # B LSL, C 中心, D USL
MEAS_COLS = list(range(9, 41))  # I..AN (实测1-32)


def _fmt_date(d):
    if isinstance(d, datetime.date):
        return f"{d.year}.{d.month:02d}.{d.day:02d}"
    return str(d)


def fill_fai(ws, product, dimensions):
    """dimensions=[(标称, 公差), ...]（来自图纸尺寸 HITL 录入）。返回项数。"""
    # 1. 治病：清旧规格 + 旧实测 + 旧日期（保留 A项次号、E-H公式、表头静态、签名）
    for r in range(ITEM_ROW0, ITEM_ROWN + 1):
        for c in SPEC_COLS + MEAS_COLS:
            ws.cell(r, c).value = None
    ws["U2"].value = None
    # 2. 表头
    ws["C2"] = product["材料名称"]   # 品类
    ws["U2"] = _fmt_date(product.get("填表日期") or datetime.date.today())  # 生成日
    # 3. 规格上下限（图纸尺寸驱动）
    for i, (n, t) in enumerate(dimensions):
        r = ITEM_ROW0 + i
        ws.cell(r, 2, n - t)   # LSL
        ws.cell(r, 3, n)       # 中心
        ws.cell(r, 4, n + t)   # USL
    # 4. 实测红槽（人工）
    for i in range(len(dimensions)):
        r = ITEM_ROW0 + i
        for c in MEAS_COLS:
            highlight_cell(ws, ws.cell(r, c).coordinate, manual=True)
    return len(dimensions)


def selfcheck_fai(ws, dimensions):
    """规格==图纸换算 + E-H公式保留。返回错误列表。"""
    errs = []
    for i, (n, t) in enumerate(dimensions):
        r = ITEM_ROW0 + i
        for c, exp in ((2, n - t), (3, n), (4, n + t)):
            got = ws.cell(r, c).value
            if got != exp:
                errs.append(f"规格 {ws.cell(r, c).coordinate}: 期望 {exp} 实得 {got!r}")
    if not str(ws["E9"].value or "").startswith("="):
        errs.append(f"E9 公式丢失: {ws['E9'].value!r}")
    if not str(ws["H9"].value or "").startswith("="):
        errs.append(f"H9(CPK) 公式丢失: {ws['H9'].value!r}")
    return errs
