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


def _maybe_int(x):
    """整数值去掉浮点尾巴(98.0→98), 与 golden 显示一致。"""
    return int(x) if isinstance(x, float) and x.is_integer() else x


def spec_limits(dim):
    """图纸尺寸 → (LSL, 中心, USL)。dim=(标称, 上公差, 下公差)，支持单边/非对称。
    实证(7样本20/20): 中心恒=(LSL+USL)/2 中点, 非标称。对称是 上公差==下公差 的特例。
    """
    n, up, lo = dim
    lsl, usl = n - lo, n + up
    return _maybe_int(lsl), _maybe_int((lsl + usl) / 2), _maybe_int(usl)


def fill_fai(ws, product, dimensions):
    """dimensions=[(标称, 上公差, 下公差), ...]（来自图纸尺寸 HITL 录入）。返回项数。"""
    # 1. 治病：清旧规格 + 旧实测 + 旧日期（保留 A项次号、E-H公式、表头静态、签名）
    for r in range(ITEM_ROW0, ITEM_ROWN + 1):
        for c in SPEC_COLS + MEAS_COLS:
            ws.cell(r, c).value = None
    ws["U2"].value = None
    # 2. 表头
    ws["C2"] = product["材料名称"]   # 品类
    ws["U2"] = _fmt_date(product.get("填表日期") or datetime.date.today())  # 生成日
    # 3. 规格上下限（图纸尺寸驱动，支持单边/非对称）
    for i, dim in enumerate(dimensions):
        lsl, center, usl = spec_limits(dim)
        r = ITEM_ROW0 + i
        ws.cell(r, 2, lsl)      # LSL = 标称−下公差
        ws.cell(r, 3, center)   # 中心 = (LSL+USL)/2 中点
        ws.cell(r, 4, usl)      # USL = 标称+上公差
    # 4. 实测红槽（人工）
    for i in range(len(dimensions)):
        r = ITEM_ROW0 + i
        for c in MEAS_COLS:
            highlight_cell(ws, ws.cell(r, c).coordinate, manual=True)
    return len(dimensions)


def selfcheck_fai(ws, dimensions):
    """规格==图纸换算 + E-H公式保留。返回错误列表。"""
    errs = []
    for i, dim in enumerate(dimensions):
        r = ITEM_ROW0 + i
        lsl, center, usl = spec_limits(dim)
        for c, exp in ((2, lsl), (3, center), (4, usl)):
            got = ws.cell(r, c).value
            if float(got if got is not None else "nan") != float(exp):
                errs.append(f"规格 {ws.cell(r, c).coordinate}: 期望 {exp} 实得 {got!r}")
    if not str(ws["E9"].value or "").startswith("="):
        errs.append(f"E9 公式丢失: {ws['E9'].value!r}")
    if not str(ws["H9"].value or "").startswith("="):
        errs.append(f"H9(CPK) 公式丢失: {ws['H9'].value!r}")
    return errs
