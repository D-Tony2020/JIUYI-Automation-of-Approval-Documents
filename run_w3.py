# -*- coding: utf-8 -*-
"""W3 图纸执行线（两段式）。

段一 openpyxl：build_upto(2) 填好封面+送样目录、无 OLE（= W3 空白参照）。
段二 COM：把本单生久图纸 PDF 嵌入第 5 页『2.图纸（生久&供应商）』为可双击 OLE。
自检：OLE 计数 0→1、COM 复开图纸表 OLEObjects==1、无外链。
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hitl.build import build_upto
from hitl.harness import assert_no_external_links
from hitl.ole_assemble import (
    extract_embedded_pdf, make_icon, embed_one, count_ole, verify_open,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, "模板", "承认书空白模板_治病.xlsx")
GOLDEN = os.path.join(ROOT, "案例材料", "承认书", "承认书", "做好的承认书",
                      "YY60039403 (J00016372) 承认书.xlsx")
DRAW = os.path.join(ROOT, "本单输入", "YY60039403_生久图纸.pdf")
OUTDIR = os.path.join(ROOT, "产出留档", "W3-图纸")
ICON = os.path.join(OUTDIR, "_icon_图纸.png")
BLANK = os.path.join(OUTDIR, "图纸_空白参照__00.xlsx")
OUT = os.path.join(OUTDIR, "图纸_嵌OLE__01.xlsx")

SHEET = "2.图纸（生久&供应商）"
DATA = {"drawing_meta": {"名称": "SB120420BLCNR009导线", "品号": "YY60039403", "版本": "A01"}}
GEO = (183.05, 266.25, 151.5, 41.85)  # 对齐 golden（锚 B11，小图标+文件名），非左上角


def main():
    os.makedirs(OUTDIR, exist_ok=True)

    # 0. 本单图纸 PDF（demo：从 golden 图纸 OLE=oleObject1.bin 抽出）
    if not os.path.exists(DRAW):
        extract_embedded_pdf(GOLDEN, "oleObject1.bin", DRAW)
        print("已抽取本单图纸 →", DRAW)

    # 段一：填好格的本（无 OLE）= 空白参照
    build_upto(TPL, BLANK, DATA, upto=2)

    # 预览图 + 段二 COM 嵌入
    make_icon(DRAW, ICON)
    embed_one(BLANK, OUT, SHEET, DRAW, ICON, GEO)

    # 自检
    errs = []
    n0, n1 = count_ole(BLANK), count_ole(OUT)
    if n1 != n0 + 1:
        errs.append(f"OLE 计数 {n0}→{n1}，应 +1")
    res = verify_open(OUT)
    if res.get(SHEET) != 1:
        errs.append(f"图纸表 OLEObjects={res.get(SHEET)}，应=1")
    got = res.get("_geo", {}).get(SHEET)
    if got is None or abs(got[0] - GEO[0]) > 5 or abs(got[1] - GEO[1]) > 5:
        errs.append(f"OLE 位置 {got} 偏离目标 ({GEO[0]},{GEO[1]})（应在表格中部 B11，非左上角）")
    assert_no_external_links(OUT)

    status = "PASS" if not errs else "FAIL"
    with open(os.path.join(OUTDIR, "_manifest.txt"), "a", encoding="utf-8") as f:
        f.write(f"图纸_嵌OLE__01\tOLE {n0}->{n1}, 图纸表={res.get(SHEET)}\t{status}\n")

    print("空白参照:", BLANK, "(图纸表无 OLE)")
    print("填入成品:", OUT)
    print(f"OLE 计数: 空白 {n0} → 成品 {n1}")
    print(f"COM 复开 OLEObjects: {res}")
    if errs:
        print("❌ 自测失败：")
        for e in errs:
            print("   -", e)
        sys.exit(1)
    print("✅ 自测通过：图纸表嵌入 1 个可双击 OLE + COM 复开无修复 + 无外链")


if __name__ == "__main__":
    main()
