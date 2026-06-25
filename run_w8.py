# -*- coding: utf-8 -*-
"""W8 总装·校验·导出：整本拼装(全cell + 样品照片N张 + 44 OLE) → 校验闸 → 导出。

段一 openpyxl: build_upto(封面/送样/材质表/FAI, highlight=False 干净终态) + 样品照片治病+摆N张。
段二 COM: 结构驱动嵌全部 44 OLE(材质表/部件承认书/材质证明/UL… 计数与布局由BOM算)。
校验闸: 齐套(漏嵌)/有效期预警/未填禁导出 + 溯源面板。
"""
import os
import sys
import io
import json
import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl
from hitl.build import build_upto
from hitl.harness import assert_no_external_links
from hitl.ole_assemble import make_icon, embed_many, count_ole
from hitl.material_table import material_ole_anchors, MAT_SHEET
from hitl import sample_photo, validate
from study.embed_structure import (count_from_bom, grid_anchors, GRID, SHEET_SHORT,
                                    matcert_anchors, MATCERT_W, MATCERT_H, spatial_order)
from study.golden_parse import parse_golden
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, "模板", "承认书空白模板_治病.xlsx")
GOLDEN = os.path.join(ROOT, "案例材料", "承认书", "承认书", "做好的承认书",
                      "YY60039403 (J00016372) 承认书.xlsx")
MANIFEST = os.path.join(ROOT, "hitl", "data", "ole_map_YY60039403.json")
BOM_JSON = os.path.join(ROOT, "hitl", "data", "demo_bom_YY60039403.json")
ICON_DIR = os.path.join(ROOT, "本单输入", "ole", "icons")
PHOTO_DIR = os.path.join(ROOT, "本单输入", "photos_demo")
OUTDIR = os.path.join(ROOT, "产出留档", "W8-总装")
CELL = os.path.join(OUTDIR, "_段一_cell+照片.xlsx")
OUT = os.path.join(OUTDIR, "承认书_总装__01.xlsx")
TODAY = datetime.date(2026, 6, 25)

DATA = {
    "drawing_meta": {"名称": "SB120420BLCNR009导线", "品号": "YY60039403", "版本": "A01"},
    "product": {"材料名称": "导线", "填表日期": TODAY},
    "bom": json.load(open(BOM_JSON, encoding="utf-8")),
    "dimensions": [(98, 5, 5), (60, 5, 5), (28, 3, 3), (2, 0.5, 0.5)],
}


def demo_photos(n):
    os.makedirs(PHOTO_DIR, exist_ok=True)
    gws = openpyxl.load_workbook(GOLDEN)[sample_photo.SHEET]
    paths = []
    for i, im in enumerate(gws._images):
        if sample_photo._anchor_col(im) == 0:
            continue
        p = os.path.join(PHOTO_DIR, f"demo_{i}.png")
        with open(p, "wb") as f:
            f.write(im._data())
        paths.append(p)
    return (paths * 3)[:n]


def build_ole_specs():
    """结构驱动的 44 OLE specs(复用 W6 逻辑): 材质表单元格定位 / 嵌入组网格 / 其余golden绝对。"""
    specs = json.load(open(MANIFEST, encoding="utf-8"))
    os.makedirs(ICON_DIR, exist_ok=True)
    for s in specs:
        s["pdf"] = os.path.join(ROOT, s["pdf"])
        s["icon"] = os.path.join(ICON_DIR, os.path.basename(s["pdf"]) + ".png")
        make_icon(s["pdf"], s["icon"])
    mt = [s for s in specs if s["sheet"].strip() == MAT_SHEET.strip()]
    for s, (r, c) in zip(mt, material_ole_anchors(DATA["bom"], mt)):
        s["row"], s["col"] = r, c
    counts = count_from_bom(DATA["bom"])
    by_sheet = defaultdict(list)
    for s in specs:
        by_sheet[s["sheet"].strip()].append(s)
    for full, short in SHEET_SHORT.items():
        grp = by_sheet.get(full, [])
        if not grp:
            continue
        grp = spatial_order(grp)           # 先按 golden 空间序排, 保文件↔标签对应
        if short == "材质证明书":           # 按零件分组(每零件其材质数张横排)
            for s, (L, T) in zip(grp, matcert_anchors(DATA["bom"])):
                s["L"], s["T"], s["W"], s["H"] = L, T, MATCERT_W, MATCERT_H
                s.pop("row", None); s.pop("col", None)
        else:                              # 部件/UL/信赖性: 单行 grid
            g = GRID[short]
            for s, (L, T) in zip(grp, grid_anchors(len(grp), **g)):
                s["L"], s["T"], s["W"], s["H"] = L, T, g["w"], g["h"]
                s.pop("row", None); s.pop("col", None)
    handled = {MAT_SHEET.strip()} | set(SHEET_SHORT.keys())
    for s in specs:
        if s["sheet"].strip() not in handled:
            s.pop("row", None); s.pop("col", None)
    return specs, counts


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    # 段一: cell(干净) + 样品照片(治病+demo 3张)
    build_upto(TPL, CELL, DATA, upto=4, highlight=False)
    wb = openpyxl.load_workbook(CELL)
    nphoto = sample_photo.fill_sample_photo(wb[sample_photo.SHEET], demo_photos(3))
    wb.save(CELL)
    # 段二: 嵌 44 OLE
    specs, counts = build_ole_specs()
    embed_many(CELL, OUT, specs)
    n_ole = count_ole(OUT)
    assert_no_external_links(OUT)

    # 校验闸
    mats = parse_golden(OUT)
    can_export, rep = validate.gate(OUT, mats, TODAY)

    print("=" * 56)
    print(f"段一: cell(干净) + 样品照片 {nphoto} 张")
    print(f"段二: OLE 嵌入 {n_ole} 个")
    print(f"嵌入组计数(BOM算): 材质证明={counts['材质证明书']} 部件承认书={counts['部件承认书']} UL={counts['UL证明']}")
    print("-" * 56 + "\n【校验闸】")
    print("  齐套漏嵌  :", rep["漏嵌"] or "✓ 无")
    print("  有效期预警:", rep["有效期预警"] or "✓ 无")
    print("  未填拦截  :", rep["未填拦截"] or "✓ 无")
    print(f"\n  → 能否导出: {'✅ 可导出' if can_export else '❌ 禁导出(未填)'}")
    print(f"\n【溯源面板】材质→报告(共 {len(validate.trace_panel(OUT))} 条), 前6:")
    for r in validate.trace_panel(OUT)[:6]:
        print(f"  {r['零件']}/{r['材质']}: {r['报告编号']} {r['报告日期']}")

    errs = []
    if n_ole != 44:
        errs.append(f"OLE {n_ole}≠44")
    if nphoto != 3:
        errs.append(f"样品照片 {nphoto}≠3")
    if not can_export:
        errs.append("校验未过(未填)")
    with open(os.path.join(OUTDIR, "_manifest.txt"), "a", encoding="utf-8") as f:
        f.write(f"承认书_总装__01\tOLE{n_ole} 照片{nphoto} 导出{can_export}\t{'PASS' if not errs else 'FAIL'}\n")
    print("\n成品:", OUT)
    if errs:
        print("❌ 自测失败:", errs); sys.exit(1)
    print("✅ 自测通过: 全cell+样品照片3张+44 OLE + 校验闸(齐套/有效期预警/未填) + 溯源 + 可导出")


if __name__ == "__main__":
    main()
