# -*- coding: utf-8 -*-
"""抽出一份承认书材质表里的**全部唯一源 PDF**（去重）。纯本地、不外发。

不做位置配对（XML 的 mc:Choice/Fallback 会让 OLE 重复、与 COM 错位）。
归属交给内容：每份 PDF 抽出后按 CAS 重叠归到 golden 材质（见 run_study）。
"""
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from hitl.ole_assemble import extract_embedded_pdf


def _natural(b):
    m = re.findall(r"\d+", b)
    return int(m[0]) if m else 0


def case_mat_ole_pdfs(xlsx_path, out_dir):
    """→ [pdf_path, ...]，材质表所有唯一 OLE 源 PDF（去重、按编号序）。"""
    os.makedirs(out_dir, exist_ok=True)
    z = zipfile.ZipFile(xlsx_path)
    names = set(z.namelist())
    wbx = z.read("xl/workbook.xml").decode("utf-8", "ignore")
    sheets = re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wbx)
    rel = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"',
                          z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "ignore")))
    code = re.sub(r"[^A-Za-z0-9]", "", os.path.basename(xlsx_path))[:12]
    for nm, rid in sheets:
        if "材质成分" not in nm.replace("&amp;", "&"):
            continue
        wsf = rel[rid]
        wsf = ("xl/" + wsf) if not wsf.startswith("xl/") else wsf
        base = os.path.basename(wsf)
        relf = f"xl/worksheets/_rels/{base}.rels"
        if relf not in names:
            return []
        targets = re.findall(r'Target="([^"]+)"', z.read(relf).decode("utf-8", "ignore"))
        bins = sorted({os.path.basename(t) for t in targets if "embeddings/oleObject" in t},
                      key=_natural)
        pdfs = []
        for b in bins:
            out = os.path.join(out_dir, f"{code}__{b.replace('.bin', '')}.pdf")
            try:
                extract_embedded_pdf(xlsx_path, b, out)
                pdfs.append(out)
            except Exception:
                pass
        return pdfs
    return []


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    p = r"案例材料\承认书\承认书\做好的承认书\YY60039403 (J00016372) 承认书.xlsx"
    pdfs = case_mat_ole_pdfs(p, r"本单输入\study_src\YY60039403")
    print(f"唯一源 PDF: {len(pdfs)}")
    for x in pdfs:
        print("  ", os.path.basename(x))
