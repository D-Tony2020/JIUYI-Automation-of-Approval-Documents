# -*- coding: utf-8 -*-
"""W1 封面 · 第一条执行线：图纸元数据 → D12/D14/D16 → 落盘 → 读回自测 → 留档。

这条线同时验通 W0 执行台（walking skeleton）。
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl
from hitl.harness import (
    load_template, save_output, assert_no_external_links, count_media,
    emit_blank_reference, diff_cells,
)
from hitl.cover import fill_cover, selfcheck_cover, COVER_SHEET

ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, "模板", "承认书空白模板_治病.xlsx")  # W0 治病后的干净模板
OUTDIR = os.path.join(ROOT, "产出留档", "W1-封面")
BLANK = os.path.join(OUTDIR, "封面_空白参照__00.xlsx")          # 空白参照（手测 diff 对照）
OUT = os.path.join(OUTDIR, "封面_图纸驱动三格__01.xlsx")
TARGET_COORDS = {"D12", "D14", "D16"}

# 本单图纸元数据（HITL 复核结果；本单 = YY60039403）
DRAWING_META = {"名称": "SB120420BLCNR009导线", "品号": "YY60039403", "版本": "A01"}


def main():
    media_before = count_media(TPL)

    # ① 空白参照（loop 起始：过同一落盘管线、不填任何值）
    emit_blank_reference(TPL, BLANK)

    # ② 填入
    wb = load_template(TPL)
    ws = wb[COVER_SHEET]
    expected = fill_cover(ws, DRAWING_META)
    save_output(wb, OUT)

    # ③ 读回断言（从落盘文件 round-trip）
    errs = selfcheck_cover(openpyxl.load_workbook(OUT)[COVER_SHEET], expected)
    assert_no_external_links(OUT)
    media_after = count_media(OUT)
    if media_after > media_before:
        errs.append(f"media 膨胀：{media_before}→{media_after}")

    # ④ 空白→填入 单元格级 diff（定位精确性自检：变更格须恰好=目标格）
    changes = diff_cells(BLANK, OUT, COVER_SHEET)
    changed = {coord for coord, _, _ in changes}
    if changed != TARGET_COORDS:
        errs.append(f"定位异常：变更格 {sorted(changed)} ≠ 目标格 {sorted(TARGET_COORDS)}")

    status = "PASS" if not errs else "FAIL"
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "_manifest.txt"), "a", encoding="utf-8") as f:
        f.write(
            f"封面_图纸驱动三格__01\t"
            f"D12={expected['D12']} D14={expected['D14']} D16={expected['D16']}\t{status}\n"
        )

    print("空白参照:", BLANK)
    print("填入成品:", OUT)
    print("填入    :", {k: expected[k] for k in ("D12", "D14", "D16")})
    print("溯源    :", expected["_source"])
    print(f"media   : {media_before}→{media_after}（不膨胀）")
    print("空白→填入 变更格（应恰好 D12/D14/D16）:")
    for coord, vb, vf in sorted(changes):
        print(f"   {coord}: {vb!r} → {vf!r}")
    if errs:
        print("❌ 自测失败：")
        for e in errs:
            print("   -", e)
        sys.exit(1)
    print("✅ 自测通过：定位精确(仅3目标格变更) + 7静态格未动 + 无外链 + media不膨胀")


if __name__ == "__main__":
    main()
