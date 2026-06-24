# -*- coding: utf-8 -*-
"""W2 送样目录执行线（累积 build）。

空白参照 = build_upto(1)（封面态，W2 前）；填入成品 = build_upto(2)（封面+送样目录）。
diff 应恰好 = 送样目录!A30；其余表零变动（跨表回归）。
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl
from hitl.harness import assert_no_external_links, diff_cells, count_media, assert_highlighted
from hitl.build import build_upto
from hitl import sample_list

ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, "模板", "承认书空白模板_治病.xlsx")
OUTDIR = os.path.join(ROOT, "产出留档", "W2-静态批")
BLANK = os.path.join(OUTDIR, "送样目录_空白参照__00.xlsx")
OUT = os.path.join(OUTDIR, "送样目录_填料号__01.xlsx")

DATA = {"drawing_meta": {"名称": "SB120420BLCNR009导线", "品号": "YY60039403", "版本": "A01"}}
SHEET = sample_list.SAMPLE_SHEET
# 这些表 W2 都不应改动（封面已在 build_upto(1) 填好，W2 不得动它）
UNCHANGED_SHEETS = ["封面", "承认书资料名细表", "附表--承认之细则", "10.车规级增加资料"]


def main():
    build_upto(TPL, BLANK, DATA, upto=1)  # 封面态
    build_upto(TPL, OUT, DATA, upto=2)    # 封面 + 送样目录

    errs = sample_list.selfcheck_sample_list(
        openpyxl.load_workbook(OUT)[SHEET], {"A30": "YY60039403"})
    assert_no_external_links(OUT)

    # ① 送样目录 diff 恰好 = {A30}
    changes = diff_cells(BLANK, OUT, SHEET)
    changed = {c for c, _, _ in changes}
    if changed != sample_list.TARGET_COORDS:
        errs.append(f"定位异常：{SHEET} 变更格 {sorted(changed)} ≠ {sorted(sample_list.TARGET_COORDS)}")
    # ② 跨表回归：其余表零变动
    for s in UNCHANGED_SHEETS:
        d = diff_cells(BLANK, OUT, s)
        if d:
            errs.append(f"{s} 不应变动，却变了 {[c for c, _, _ in d]}")
    # ③ 高亮自检
    errs += assert_highlighted(openpyxl.load_workbook(OUT)[SHEET], sample_list.TARGET_COORDS)

    status = "PASS" if not errs else "FAIL"
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "_manifest.txt"), "a", encoding="utf-8") as f:
        f.write(f"送样目录_填料号__01\tA30=YY60039403\t{status}\n")

    print("空白参照:", BLANK)
    print("填入成品:", OUT)
    print("media   :", count_media(OUT))
    print("送样目录 空白→填入 变更格（应恰好 A30）:")
    for coord, vb, vf in sorted(changes):
        print(f"   {coord}: {vb!r} → {vf!r}")
    if errs:
        print("❌ 自测失败：")
        for e in errs:
            print("   -", e)
        sys.exit(1)
    print("✅ 自测通过：送样目录仅 A30 变更 + 判定栏/厂商/制定/核准 静态在位 + 其余表零变动 + 无外链")


if __name__ == "__main__":
    main()
