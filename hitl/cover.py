# -*- coding: utf-8 -*-
"""W1 封面：按《W1-封面 收敛规格》仅填 D12/D14/D16（图纸驱动三格）。

签认结论：
- D12 = 图纸名称尾部品类词（可扩展词典）
- D14 = 图纸品号（直取） / D16 = 图纸版本（直取）
- 签字人 C21/D21/E21 与供应商档案 C27/C29/C33 = 模板静态，工具不碰（自检其未被改动）
"""
from .harness import write_cell, read_cell
from .category import extract_category

COVER_SHEET = "封面"

# 模板静态格（自检基线：不可被改动）
STATIC_CELLS = {
    "B4": "宁波生久科技有限公司",
    "B10": "材料承认书 Rev3.1版本 ",
    "C21": "Leven", "D21": "王立均", "E21": "张启宇",
    "C27": "宁波市余姚市大隐镇学士桥村生久老厂房三楼久益电子有限公司",
    "C29": 13486459752,
    "C33": "joyielec @163.com",
}


def fill_cover(ws, drawing_meta):
    """填封面三格。drawing_meta = {名称, 品号, 版本}（图纸元数据 HITL 复核结果）。

    返回 expected：含三格目标值 + 溯源。品类词词典外则抛错（交人工）。
    """
    cat, ok = extract_category(drawing_meta["名称"])
    if not ok:
        raise ValueError(
            f"品类词未识别，需人工确认：{drawing_meta['名称']!r}（不在词典内）"
        )
    write_cell(ws, "D12", cat)
    write_cell(ws, "D14", drawing_meta["品号"])
    write_cell(ws, "D16", drawing_meta["版本"])
    return {
        "D12": cat, "D14": drawing_meta["品号"], "D16": drawing_meta["版本"],
        "_source": {"D12": "图纸.名称→品类词", "D14": "图纸.品号", "D16": "图纸.版本REV"},
    }


def selfcheck_cover(ws, expected):
    """读回断言：3 目标格==期望 且 7 个静态格未被改动。返回错误列表（空=通过）。"""
    errs = []
    for coord in ("D12", "D14", "D16"):
        got = read_cell(ws, coord)
        if got != expected[coord]:
            errs.append(f"目标格 {coord}：期望 {expected[coord]!r}，实得 {got!r}")
    for coord, val in STATIC_CELLS.items():
        got = read_cell(ws, coord)
        if got != val:
            errs.append(f"静态格 {coord} 被改动：期望 {val!r}，实得 {got!r}")
    return errs
