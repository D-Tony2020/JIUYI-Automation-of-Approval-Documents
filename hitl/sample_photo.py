# -*- coding: utf-8 -*-
"""W7 样品照片（第4标签页『4.样品照片（多角度）』）：治病 + 人工红槽。

照片=浮动嵌入图（非OLE非cell），段一 openpyxl 处理。
- 治病：删 golden 残留的成品照（按锚点 col>0 判，保留 col0 的生久 LOGO）。
- 红槽：照片区浅红填充 + 红字标签『待人工插入成品照片』。纯人工，未插禁导出。
实证 7 案：恒 4 图（1 LOGO + 3 成品照），照片数固定、不随产品变。
"""
from openpyxl.styles import PatternFill, Font, Alignment

SHEET = "4.样品照片（多角度）"
RED_FILL = PatternFill("solid", fgColor="FFC7CE")          # 浅红=待人工填
RED_FONT = Font(name="宋体", size=12, bold=True, color="9C0006")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ZONE_ROWS = range(11, 23)        # 照片区行（1-indexed）
ZONE_COLS = ("B", "C")
LABEL_CELL = "B11"
LABEL = "⚠ 待人工插入成品照片（多角度，≥3 张）— 未插禁导出"


def _anchor_col(im):
    a = getattr(im, "anchor", None)
    return getattr(getattr(a, "_from", None), "col", 0)


def fill_sample_photo(ws):
    """删成品照(留LOGO) + 标红槽。返回删除的成品照数。"""
    keep, removed = [], 0
    for im in ws._images:
        if _anchor_col(im) == 0:        # col0 = 生久 LOGO，保留
            keep.append(im)
        else:
            removed += 1
    ws._images = keep
    for r in ZONE_ROWS:
        for c in ZONE_COLS:
            ws[f"{c}{r}"].fill = RED_FILL
    ws[LABEL_CELL] = LABEL
    ws[LABEL_CELL].font = RED_FONT
    ws[LABEL_CELL].alignment = CENTER
    return removed


def selfcheck_sample_photo(ws):
    errs = []
    non_logo = sum(1 for im in ws._images if _anchor_col(im) != 0)
    if non_logo:
        errs.append(f"成品照未清净：仍有非LOGO图×{non_logo}")
    if len(ws._images) < 1:
        errs.append("LOGO 被误删")
    fill = ws[LABEL_CELL].fill
    if not (fill and fill.fgColor and "FFC7CE" in str(fill.fgColor.rgb)):
        errs.append("照片区未标红")
    if "待人工" not in str(ws[LABEL_CELL].value or ""):
        errs.append("缺待填标签")
    return errs
