# -*- coding: utf-8 -*-
"""W2 送样承认书目录：仅填 A30 料号；厂商/制定/核准/判定栏=模板静态、断言基线。

签认结论：只填唯一空格 A30=料号（=封面 D14=图纸品号）；其余 117 格静态不碰。
"""
from .harness import write_cell, read_cell

SAMPLE_SHEET = "1.送样承认书目录"
TARGET_COORDS = {"A30"}

# 模板静态基线（非车规模式；工具不碰，断言其在位防换错模板/漏判车规）
_V_ROWS = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 23, 24, 25, 27]
_NA_ROWS = [18, 19, 20, 21, 22, 26]
JUDGMENT_BASELINE = {**{f"E{r}": "V" for r in _V_ROWS},
                     **{f"E{r}": "N/A" for r in _NA_ROWS}}
STATIC_BASELINE = {"B30": "久益", "D30": "否", "E30": "Leven", "F30": "王立均"}


def fill_sample_list(ws, 料号):
    """仅填料号 A30。"""
    write_cell(ws, "A30", 料号)
    return {"A30": 料号, "_source": {"A30": "图纸.品号(=封面D14)"}}


def selfcheck_sample_list(ws, expected):
    """读回 A30 + 静态基线（判定栏 E7-E27 + 厂商/制定/核准/是否车规）未被改动。"""
    errs = []
    if read_cell(ws, "A30") != expected["A30"]:
        errs.append(f"A30: 期望 {expected['A30']!r}，实得 {read_cell(ws, 'A30')!r}")
    for coord, val in {**JUDGMENT_BASELINE, **STATIC_BASELINE}.items():
        got = read_cell(ws, coord)
        if got != val:
            errs.append(f"静态基线 {coord}: 期望 {val!r}，实得 {got!r}")
    return errs
