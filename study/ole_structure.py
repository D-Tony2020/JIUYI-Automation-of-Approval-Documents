# -*- coding: utf-8 -*-
"""实证: 7案各『OLE嵌入组表』的槽位数 × 该案BOM结构(零件数/材质数)。找槽位数的驱动变量。

嵌入组表: 2.图纸 / 3.供应商部件承认书 / 6.信赖性 / 7.材质成分(已另研) /
          8.材质证明书 / 9.UL / 11.包装 / 12.出货。纯本地、不外发。
"""
import os
import re
import sys
import glob
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from study.golden_parse import parse_golden

# 关注的嵌入组表（关键词 → 短名）
SHEETS = [("2.图", "图纸"), ("3.供应商部件", "部件承认书"), ("6.信赖", "信赖性"),
          ("8.材质证明", "材质证明书"), ("9.UL", "UL证明"), ("9.ul", "UL证明"),
          ("11.包装", "包装"), ("12.出货", "出货")]


def ole_count_per_sheet(xlsx):
    """→ {短名: OLE数}（按 worksheet rels 数 embeddings/oleObject）。"""
    z = zipfile.ZipFile(xlsx)
    names = set(z.namelist())
    wbx = z.read("xl/workbook.xml").decode("utf-8", "ignore")
    sheets = re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wbx)
    rel = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"',
                          z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "ignore")))
    out = {}
    for nm, rid in sheets:
        nm2 = nm.replace("&amp;", "&")
        short = None
        for kw, s in SHEETS:
            if nm2.strip().startswith(kw) or kw in nm2:
                short = s
                break
        if not short:
            continue
        wsf = rel[rid]
        wsf = ("xl/" + wsf) if not wsf.startswith("xl/") else wsf
        base = os.path.basename(wsf)
        relf = f"xl/worksheets/_rels/{base}.rels"
        if relf not in names:
            out[short] = 0
            continue
        tgts = re.findall(r'Target="([^"]+)"', z.read(relf).decode("utf-8", "ignore"))
        out[short] = len({os.path.basename(t) for t in tgts if "embeddings/oleObject" in t})
    return out


def bom_structure(xlsx):
    """→ (零件数, 材质数)。零件=材质表里 distinct 零件; 材质=材质数。"""
    mats = parse_golden(xlsx)
    parts = {(m["零件"] or "").strip() for m in mats if (m["零件"] or "").strip()}
    return len(parts), len(mats), sorted(parts)


def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    cases = sorted([p for p in glob.glob(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                     "案例材料", "承认书", "参考用承诺书集", "*.xlsx"))
        if not os.path.basename(p).startswith("~$")])
    cols = ["图纸", "部件承认书", "信赖性", "材质证明书", "UL证明", "包装", "出货"]
    hdr = f"{'案例':12}{'零件':>4}{'材质':>4} | " + " ".join(f"{c:>10}" for c in cols)
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for x in cases:
        cnt = ole_count_per_sheet(x)
        nparts, nmats, parts = bom_structure(x)
        rows.append((os.path.basename(x)[:10], nparts, nmats, cnt, parts))
        line = f"{os.path.basename(x)[:10]:12}{nparts:>4}{nmats:>4} | " + \
               " ".join(f"{cnt.get(c,0):>10}" for c in cols)
        print(line)
    print("\n各案零件清单:")
    for code, np_, nm_, cnt, parts in rows:
        print(f"  {code}: {parts}")


if __name__ == "__main__":
    main()
