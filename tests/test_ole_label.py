# -*- coding: utf-8 -*-
"""OLE 物料标签(#8): make_icon 把料名/零件名烤进图标底部色带; specs 携带 label。

标签↔pdf 一一对齐由构造保证(每图标=自己 pdf+自己 label, 装配时序号前缀防同 pdf 覆盖)。
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import fitz

from hitl.ole_assemble import make_icon
from hitl.placement_plan import material_specs


def test_make_icon_label色带(tmp_path):
    from PIL import Image
    pdf = str(tmp_path / "t.pdf")
    doc = fitz.open(); doc.new_page(width=160, height=200)
    doc.save(pdf); doc.close()
    png = str(tmp_path / "t.png")
    make_icon(pdf, png, label="镀锡铜 RoHS")
    assert os.path.exists(png)
    im = Image.open(png).convert("RGB")
    W, H = im.size
    px = im.getpixel((W // 2, H - 3))             # 底部中心=标签色带(深 31,41,55)
    assert sum(px) < 220


def test_make_icon_无label不崩(tmp_path):
    pdf = str(tmp_path / "t.pdf")
    doc = fitz.open(); doc.new_page(width=120, height=150); doc.save(pdf); doc.close()
    png = str(tmp_path / "t.png")
    assert make_icon(pdf, png) == png and os.path.exists(png)   # label=None 照常出图标


def test_specs带label():
    s2 = {"_sheet_names": ["7.材质成分展开表 ", "8.材质证明书"],
          "materials": [{"零件": "导线", "材质": "镀锡铜", "材质类别": "线材",
                         "成份": [{"成份名称": "Cu", "CAS": "7440-50-8", "重量%": "0.99"}],
                         "files": {"MSDS": "DXT.pdf", "RoHS": ["DXT_R.pdf"]}}]}
    specs, _, _ = material_specs(s2, "matdir")
    mt = [s for s in specs if s["short"] == "材质表"]
    cert = [s for s in specs if s["short"] == "材质证明"]
    assert all("镀锡铜" in s["label"] for s in mt)        # 材质表标签=料名+类型
    assert cert and cert[0]["label"] == "镀锡铜"          # 材质证明标签=料名
