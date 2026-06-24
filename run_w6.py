# -*- coding: utf-8 -*-
"""W6 全 OLE 装配（段二 COM 终态）：cell填完的工作簿 → 一次性嵌全部 44 个 OLE。

段一 build_upto(4) 填完所有 cell(封面/送样/材质表/FAI) → 段二 embed_many 嵌 44 OLE。
自检：OLE 计数==44、COM 复开各表计数对、无修复弹窗、无外链。
"""
import os
import sys
import io
import json
import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hitl.build import build_upto
from hitl.harness import assert_no_external_links
from hitl.ole_assemble import make_icon, embed_many, count_ole, verify_open
from hitl.material_table import material_ole_anchors, MAT_SHEET
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, "模板", "承认书空白模板_治病.xlsx")
MANIFEST = os.path.join(ROOT, "hitl", "data", "ole_map_YY60039403.json")
BOM_JSON = os.path.join(ROOT, "hitl", "data", "demo_bom_YY60039403.json")
ICON_DIR = os.path.join(ROOT, "本单输入", "ole", "icons")
OUTDIR = os.path.join(ROOT, "产出留档", "W6-全OLE")
CELL = os.path.join(OUTDIR, "_cell_只填格.xlsx")     # 段一中间产物
OUT = os.path.join(OUTDIR, "全本_含44OLE__01.xlsx")  # 段二终态

DATA = {
    "drawing_meta": {"名称": "SB120420BLCNR009导线", "品号": "YY60039403", "版本": "A01"},
    "product": {"材料名称": "导线", "填表日期": datetime.date(2026, 6, 24)},
    "bom": json.load(open(BOM_JSON, encoding="utf-8")),
    "dimensions": [(98, 5, 5), (60, 5, 5), (28, 3, 3), (2, 0.5, 0.5)],
}


def main():
    os.makedirs(ICON_DIR, exist_ok=True)
    specs = json.load(open(MANIFEST, encoding="utf-8"))

    # ⭐材质表 OLE 位置由结构推导(compute_layout 块首行 + K/L/Y 列), 非套 golden 绝对位置
    mt_specs = [s for s in specs if s["sheet"].strip() == MAT_SHEET.strip()]
    mt_anchors = material_ole_anchors(DATA["bom"], mt_specs)
    ai = 0
    for spec in specs:
        if spec["sheet"].strip() == MAT_SHEET.strip():
            spec["row"], spec["col"] = mt_anchors[ai]
            ai += 1

    # 预览图标(每个源 PDF 首页渲染) + 检测空/损坏源
    import fitz
    bad = []
    for spec in specs:
        spec["pdf"] = os.path.join(ROOT, spec["pdf"])
        spec["icon"] = os.path.join(ICON_DIR, os.path.basename(spec["pdf"]) + ".png")
        try:
            d = fitz.open(spec["pdf"]); pc = d.page_count; d.close()
        except Exception:
            pc = 0
        if pc == 0:
            bad.append((spec["sheet"].strip(), spec["bin"], os.path.basename(spec["pdf"])))
        make_icon(spec["pdf"], spec["icon"])
    if bad:
        print(f"⚠️ {len(bad)} 个源PDF 空/损坏(用占位图标, 待查抽取):")
        for b in bad:
            print("   ", b)
    print(f"材质表 OLE 结构落位(块首行+K/L/Y): {sorted(set(mt_anchors))}")

    # 段一：填完所有 cell（无 OLE）
    build_upto(TPL, CELL, DATA, upto=4)
    n_before = count_ole(CELL)

    # 段二：一次性嵌全部 44 个 OLE
    embed_many(CELL, OUT, specs)

    # 自检
    errs = []
    n_after = count_ole(OUT)
    want = len(specs)
    if n_after != want:
        errs.append(f"OLE 计数 {n_after}，应 {want}")
    if n_before != 0:
        errs.append(f"段一 cell 工作簿不应有 OLE，实得 {n_before}")
    res = verify_open(OUT)
    assert_no_external_links(OUT)
    # 各表 OLE 数对清单
    want_by_sheet = Counter(s["sheet"].strip() for s in specs)
    got_by_sheet = {k.strip(): v for k, v in res.items() if not k.startswith("_")}
    for sh, c in want_by_sheet.items():
        if got_by_sheet.get(sh) != c:
            errs.append(f"[{sh}] OLE 数 {got_by_sheet.get(sh)}，应 {c}")

    status = "PASS" if not errs else "FAIL"
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "_manifest.txt"), "a", encoding="utf-8") as f:
        f.write(f"全本_含44OLE__01\tOLE {n_before}->{n_after}/{want}\t{status}\n")

    print("段一 cell 工作簿:", CELL, f"(OLE={n_before})")
    print("段二 全本成品  :", OUT)
    print(f"OLE 计数: {n_before} → {n_after} (目标 {want})")
    print("COM 复开各表 OLE 数:")
    for k, v in sorted(got_by_sheet.items()):
        print(f"   {k}: {v}")
    if errs:
        print("❌ 自测失败：")
        for e in errs:
            print("   -", e)
        sys.exit(1)
    print("✅ 自测通过：44 个 OLE 全嵌入 + 各表计数对 + COM复开无修复 + 无外链")


if __name__ == "__main__":
    main()
