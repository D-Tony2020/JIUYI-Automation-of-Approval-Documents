# -*- coding: utf-8 -*-
"""W1 封面执行线（累积 build, upto=1）。

空白参照 = build_upto(0)（治病模板+动态格高亮、零填充）；
填入成品 = build_upto(1)（封面三格 + 高亮）。diff 应恰好 = {D12,D14,D16}。
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl
from hitl.harness import assert_no_external_links, diff_cells, count_media, assert_highlighted
from hitl.build import build_upto
from hitl import cover

ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, "模板", "承认书空白模板_治病.xlsx")
OUTDIR = os.path.join(ROOT, "产出留档", "W1-封面")
BLANK = os.path.join(OUTDIR, "封面_空白参照__00.xlsx")
OUT = os.path.join(OUTDIR, "封面_图纸驱动三格__01.xlsx")

DATA = {"drawing_meta": {"名称": "SB120420BLCNR009导线", "品号": "YY60039403", "版本": "A01"}}
SHEET = cover.COVER_SHEET
TARGET = {"D12", "D14", "D16"}


def main():
    build_upto(TPL, BLANK, DATA, upto=0)  # 空白参照（高亮、零填充）
    build_upto(TPL, OUT, DATA, upto=1)    # 封面

    errs = cover.selfcheck_cover(
        openpyxl.load_workbook(OUT)[SHEET],
        {"D12": "导线", "D14": "YY60039403", "D16": "A01"})
    assert_no_external_links(OUT)

    out_ws = openpyxl.load_workbook(OUT)[SHEET]
    changes = diff_cells(BLANK, OUT, SHEET)
    changed = {c for c, _, _ in changes}
    if changed != TARGET:
        errs.append(f"定位异常：{SHEET} 变更格 {sorted(changed)} ≠ {sorted(TARGET)}")
    errs += assert_highlighted(out_ws, TARGET)

    status = "PASS" if not errs else "FAIL"
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "_manifest.txt"), "a", encoding="utf-8") as f:
        f.write(f"封面_图纸驱动三格__01\t{ {c: vf for c, _, vf in changes} }\t{status}\n")

    print("空白参照:", BLANK)
    print("填入成品:", OUT)
    print("media   :", count_media(OUT))
    print("封面 空白→填入 变更格（应恰好 D12/D14/D16）:")
    for coord, vb, vf in sorted(changes):
        print(f"   {coord}: {vb!r} → {vf!r}")
    if errs:
        print("❌ 自测失败：")
        for e in errs:
            print("   -", e)
        sys.exit(1)
    print("✅ 自测通过：封面仅3目标格变更 + 7静态格未动 + 无外链 + 动态格已高亮")


if __name__ == "__main__":
    main()
