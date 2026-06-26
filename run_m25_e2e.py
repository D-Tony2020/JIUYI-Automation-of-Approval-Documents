# -*- coding: utf-8 -*-
"""M2.5 导出 e2e: 注样品照片 → assemble_job(读 state 装配) → 断言 OLE 复开 + 照片落位 + LOGO 保留。

复用导出端点实跑的 assemble_job(子进程入口同款)。用法: python run_m25_e2e.py [job=demo403]
"""
import glob
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fitz
import openpyxl
from app import state
from hitl.assemble_order import assemble_job
from hitl.sample_photo import SHEET as PHOTO_SHEET, _anchor_col


def main():
    job = sys.argv[1] if len(sys.argv) > 1 else "demo403"
    pdir = state.photos_dir(job)
    for n, (w, h) in [("e2e_竖.png", (300, 450)), ("e2e_横.png", (600, 300))]:   # 竖+横各一, 验保比例布局
        d = fitz.open(); pg = d.new_page(width=w, height=h)
        pg.draw_rect(pg.rect, fill=(0.85, 0.92, 1.0)); pg.get_pixmap().save(os.path.join(pdir, n)); d.close()
    print(f"=== M2.5 导出 e2e ({job}) ===")
    r = assemble_job(job)
    if not r.get("ok"):
        print("❌ 装配失败:", r.get("err")); return
    wb = openpyxl.load_workbook(r["out"])
    ws = [wb[s] for s in wb.sheetnames if s.strip() == PHOTO_SHEET.strip()][0]
    nph = sum(1 for im in ws._images if _anchor_col(im) != 0)
    nlogo = sum(1 for im in ws._images if _anchor_col(im) == 0)
    ok = r["ole"] == r["opens"] and nph >= 2 and nlogo >= 1
    print(f"{'✅' if ok else '⚠️'} OLE嵌{r['ole']}/复开{r['opens']} | 样品照片{nph}张+LOGO{nlogo} | 产物 {os.path.basename(r['out'])}")
    print("  各表:", r["by_sheet"])


if __name__ == "__main__":
    main()
