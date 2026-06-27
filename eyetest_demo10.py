# -*- coding: utf-8 -*-
"""眼测: 逐单渲染 我们的段一材质表 vs golden材质表, 左右拼图供同页对比。
前置: 先跑 run_demo10_e2e.py(产 .work/demo10/<code>/<code>_matsheet.xlsx)。
COM(WPS)导出xlsx→PDF→fitz渲染材质表页→PIL左右拼。慢, 建议后台。
"""
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import fitz
from PIL import Image

from hitl.ole_assemble import com_session

CASES = os.path.join(ROOT, "案例材料", "承认书", "参考用承诺书集")
OUT = os.path.join(ROOT, ".work", "demo10")


def _golden(code):
    for g in glob.glob(os.path.join(CASES, "*.xlsx")):
        if code in os.path.basename(g) and not os.path.basename(g).startswith("~$"):
            return g
    return None


def _export_pdf(xl, xlsx, pdf):
    wb = xl.Workbooks.Open(os.path.abspath(xlsx))
    if os.path.exists(pdf):
        os.remove(pdf)
    wb.ExportAsFixedFormat(0, os.path.abspath(pdf))
    wb.Close(SaveChanges=False)


def _matsheet_png(pdf, png, dpi=140):
    d = fitz.open(pdf)
    pno = None
    for i in range(d.page_count):
        t = d[i].get_text()
        if "有害物质调查" in t and ("供货商类别" in t or "CAS" in t.upper()):  # 真材质表(非目录提及)
            pno = i
            break
    if pno is None:                          # 兜底: 含成分关键词的页
        for i in range(d.page_count):
            if "成份名" in d[i].get_text() or "Substance" in d[i].get_text():
                pno = i; break
    d[pno if pno is not None else 0].get_pixmap(dpi=dpi).save(png)
    d.close()


def _stitch(our_png, gold_png, out_png, code):
    a, b = Image.open(our_png).convert("RGB"), Image.open(gold_png).convert("RGB")
    h = max(a.height, b.height)
    a = a.resize((int(a.width * h / a.height), h)); b = b.resize((int(b.width * h / b.height), h))
    pad, top = 16, 34
    canvas = Image.new("RGB", (a.width + b.width + pad * 3, h + top + pad), (255, 255, 255))
    canvas.paste(a, (pad, top)); canvas.paste(b, (a.width + pad * 2, top))
    try:
        from PIL import ImageDraw, ImageFont
        dr = ImageDraw.Draw(canvas)
        f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 18)
        dr.text((pad, 8), f"我们的输出 — {code}", fill=(180, 0, 0), font=f)
        dr.text((a.width + pad * 2, 8), f"golden(原承诺书) — {code}", fill=(0, 100, 0), font=f)
    except Exception:
        pass
    canvas.save(out_png)


def main():
    codes = sys.argv[1:] or json.load(open(os.path.join(ROOT, ".work", "_demo10_codes.json")))
    done = []
    with com_session() as xl:
        for code in codes:
            our = os.path.join(OUT, code, code + "_matsheet.xlsx")
            gp = _golden(code)
            if not os.path.exists(our) or not gp:
                print(f"⚠️ {code}: 缺 our/golden"); continue
            od = os.path.join(OUT, code)
            try:
                _export_pdf(xl, our, os.path.join(od, "our.pdf"))
                _export_pdf(xl, gp, os.path.join(od, "gold.pdf"))
                _matsheet_png(os.path.join(od, "our.pdf"), os.path.join(od, "our_mat.png"))
                _matsheet_png(os.path.join(od, "gold.pdf"), os.path.join(od, "gold_mat.png"))
                out = os.path.join(OUT, f"eyetest_{code}.png")
                _stitch(os.path.join(od, "our_mat.png"), os.path.join(od, "gold_mat.png"), out, code)
                done.append(out); print(f"✅ {code}: {out}")
            except Exception as e:
                print(f"❌ {code}: {str(e)[:80]}")
    print(f"\n眼测拼图 {len(done)} 张, 在 .work/demo10/eyetest_*.png")


if __name__ == "__main__":
    main()
