# -*- coding: utf-8 -*-
"""W7 样品照片执行线：治病(删golden成品照) + 人工红槽。段一 openpyxl。

空白参照=治病模板原样(留残照)；成品=清照+红槽。自检：成品照已清、LOGO在、红槽+标签。
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl
from hitl.harness import assert_no_external_links
from hitl import sample_photo

ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, "模板", "承认书空白模板_治病.xlsx")
OUTDIR = os.path.join(ROOT, "产出留档", "W7-样品照片")
OUT = os.path.join(OUTDIR, "样品照片_红槽__01.xlsx")
SHEET = sample_photo.SHEET


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    wb = openpyxl.load_workbook(TPL)
    ws = wb[SHEET]
    before = len(ws._images)
    removed = sample_photo.fill_sample_photo(ws)
    after = len(ws._images)
    if os.path.exists(OUT):
        os.remove(OUT)
    wb.save(OUT)

    out = openpyxl.load_workbook(OUT)[SHEET]
    errs = sample_photo.selfcheck_sample_photo(out)
    assert_no_external_links(OUT)

    status = "PASS" if not errs else "FAIL"
    with open(os.path.join(OUTDIR, "_manifest.txt"), "a", encoding="utf-8") as f:
        f.write(f"样品照片_红槽__01\t图 {before}->{after}(删成品照{removed})\t{status}\n")

    print("填入成品:", OUT)
    print(f"图片: {before} → {after}（删成品照 {removed} 张，留 LOGO {after}）")
    print(f"红槽标签 B11: {out['B11'].value}")
    print(f"照片区红填充: B12={out['B12'].fill.fgColor.rgb} C18={out['C18'].fill.fgColor.rgb}")
    if errs:
        print("❌ 自测失败：")
        for e in errs:
            print("   -", e)
        sys.exit(1)
    print("✅ 自测通过：成品照已清 + LOGO在 + 照片区红槽 + 标签 + 无外链")


if __name__ == "__main__":
    main()
