# -*- coding: utf-8 -*-
"""W1 封面：按《W1-封面 收敛规格》仅填 D12/D14/D16（图纸驱动三格）。

签认结论：
- D12 = 图纸名称尾部品类词（可扩展词典）
- D14 = 图纸品号（直取） / D16 = 图纸版本（直取）
- 签字人 C21/D21/E21 与供应商档案 C27/C29/C33 = 模板静态，工具不碰（自检其未被改动）
"""
from .harness import write_cell, read_cell
from .category import extract_category, normalize_name

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
    """填封面三格。drawing_meta = {名称, 品号, 版本, 品类?}（图纸元数据 HITL 复核结果）。

    软进硬出: 永不 raise。品类词来源优先级 品类(操作员确认) > 名称归一+词典+学习;
    全失败→D12 暂留归一后原文(老板拍板A·留痕软门), expected 标 _unknown_category=True 供上层软预警/硬门判定。
    """
    name = str(drawing_meta.get("名称") or "")
    override = str(drawing_meta.get("品类") or "").strip()
    if override:
        cat, unknown = override, False                    # 操作员现场确认值, 直采
    else:
        cat, ok = extract_category(name)
        unknown = not ok
        if unknown:
            cat = normalize_name(name)                    # 暂留归一原文(留痕), 由导出端硬门保证非空
    write_cell(ws, "D12", cat)
    write_cell(ws, "D14", drawing_meta["品号"])
    write_cell(ws, "D16", drawing_meta["版本"])
    return {
        "D12": cat, "D14": drawing_meta["品号"], "D16": drawing_meta["版本"],
        "_unknown_category": unknown, "_raw_name": name,
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
