# -*- coding: utf-8 -*-
"""S-OLE 预研：OLE 源文件迁入（嵌入可双击打开 + PNG 预览）。
方法已验证：Package + Filename + IconFileName(PNG) + Interactive=False。
本脚本：①44对象批量压测(计划点名的唯一未知) ②真产物嵌入 ③复开验证(计数/无修复)。
注意：嵌入是本地文件操作，不出网，可用真实源 PDF。
"""
import os, sys, io, time, zipfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pythoncom
import win32com.client as w
import fitz
from contextlib import contextmanager

ROOT = r"D:\Desktop\Moore 工业智能\久益\久益-承认书自动化"
锡 = os.path.join(ROOT, r"案例材料\承认书\承认书\锡丝")
ROHS = os.path.join(锡, "锡线ROHS英文版 SZXEC25002243403 2025.06.30.pdf")
MSDS = os.path.join(锡, "07CU物質安全資料表无铅锡线 Material Safe Data Sheet(1).pdf")
FILLED = os.path.join(ROOT, r"模板\填充示例_锡+热缩管.xlsx")
OUT_STRESS = os.path.join(ROOT, r"模板\_ole_stress44.xlsx")
OUT_REAL = os.path.join(ROOT, r"模板\填充示例_带OLE.xlsx")
ICON = os.path.join(ROOT, r"模板\_icon_tmp.png")


@contextmanager
def com_session():
    pythoncom.CoInitialize()
    xl = w.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    for attr in ("AskToUpdateLinks", "Interactive"):
        try:
            setattr(xl, attr, False)
        except Exception:
            pass
    try:
        yield xl
    finally:
        try:
            xl.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def make_icon(pdf, out_png, dpi=96):
    d = fitz.open(pdf)
    d[0].get_pixmap(dpi=dpi).save(out_png)
    d.close()
    return out_png


def embed(ws, src, png, left, top, w_=110, h_=130):
    return ws.OLEObjects().Add(ClassType="Package", Filename=src, Link=False,
                               DisplayAsIcon=True, IconFileName=png, IconIndex=0,
                               Left=left, Top=top, Width=w_, Height=h_)


def zip_embeddings(path):
    return len([n for n in zipfile.ZipFile(path).namelist() if "embeddings/oleObject" in n])


def stress_44():
    print("\n=== S-OLE 44对象批量压测 ===")
    make_icon(ROHS, ICON)
    t0 = time.time()
    with com_session() as xl:
        wb = xl.Workbooks.Add()
        ws = wb.Worksheets(1)
        for i in range(44):
            row, col = divmod(i, 8)
            embed(ws, ROHS, ICON, left=10 + col * 120, top=10 + row * 140)
            if (i + 1) % 11 == 0:
                print(f"   已嵌 {i+1}/44  累计 {time.time()-t0:.1f}s", flush=True)
        if os.path.exists(OUT_STRESS):
            os.remove(OUT_STRESS)
        wb.SaveAs(OUT_STRESS, FileFormat=51)
        wb.Close(SaveChanges=False)
    dt = time.time() - t0
    print(f"   44对象完成，用时 {dt:.1f}s，平均 {dt/44:.2f}s/个；embeddings={zip_embeddings(OUT_STRESS)}")


def embed_real():
    print("\n=== 真产物嵌入(锡丝RoHS+MSDS → 8.材质证明书) ===")
    icon_rohs = make_icon(ROHS, os.path.join(ROOT, r"模板\_icon_rohs.png"))
    icon_msds = make_icon(MSDS, os.path.join(ROOT, r"模板\_icon_msds.png"))
    if os.path.exists(OUT_REAL):
        os.remove(OUT_REAL)
    with com_session() as xl:
        wb = xl.Workbooks.Open(FILLED)
        ws = None
        for sh in wb.Worksheets:
            if sh.Name.startswith("8.材质证明"):
                ws = sh
                break
        embed(ws, ROHS, icon_rohs, left=20, top=200)
        embed(ws, MSDS, icon_msds, left=160, top=200)
        wb.SaveAs(OUT_REAL, FileFormat=51)
        wb.Close(SaveChanges=False)
    print(f"   嵌入完成 -> {OUT_REAL}；embeddings={zip_embeddings(OUT_REAL)}")


def verify(path):
    print(f"\n=== 复开验证 {os.path.basename(path)} ===")
    with com_session() as xl:
        wb = xl.Workbooks.Open(path, UpdateLinks=0, ReadOnly=True)
        print("   打开无异常(无修复弹窗)")
        total = 0
        for ws in wb.Worksheets:
            try:
                c = ws.OLEObjects().Count
            except Exception:
                c = 0
            if c:
                print(f"   [{ws.Name}] OLEObjects={c}")
                total += c
        print(f"   OLEObjects 合计={total}")
        wb.Close(SaveChanges=False)


if __name__ == "__main__":
    stress_44()
    verify(OUT_STRESS)
    embed_real()
    verify(OUT_REAL)
    print("\n✅ S-OLE 预研完成")
