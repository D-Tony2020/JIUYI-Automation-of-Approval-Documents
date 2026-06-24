# -*- coding: utf-8 -*-
"""M7 迁入：把各料类源文件按装配族映射，嵌入承认书对应 sheet（OLE 可双击 + 可读页面预览）。
嵌入是本地文件操作，不出网，可用真实源 PDF。
预览用每份 PDF 首页栅格化的 PNG（清晰可读），尺寸放大到可辨识。
"""
import os, sys, io, time, zipfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pythoncom
import win32com.client as w
import fitz
from contextlib import contextmanager

ROOT = r"D:\Desktop\Moore 工业智能\久益\久益-承认书自动化"
LIB = os.path.join(ROOT, r"案例材料\承认书\承认书")
BASE = os.path.join(ROOT, r"模板\填充示例_锡+热缩管.xlsx")
OUT = os.path.join(ROOT, r"模板\填充示例_全装配.xlsx")
ICONDIR = os.path.join(ROOT, r"模板\_icons")
os.makedirs(ICONDIR, exist_ok=True)

# 装配族映射：sheet 名前缀 → [(源PDF相对LIB路径, 标签)]
MAP = {
    "2.图纸": [(os.path.join(ROOT, r"模板\_sheet2_drawing.pdf"), "生久图纸 YY60039403")],
    "3.供应商部件承认书": [
        (r"端子胶壳\联和\A2501(XH)规格书V2.1.pdf", "端子胶壳 联和 规格书"),
        (r"套管\四川领飞热缩套管承认书.pdf", "套管 领飞 承认书"),
    ],
    "6.信赖性测试报告": [
        (r"端子胶壳\联和\XH-T21盐雾报告.pdf", "端子 盐雾报告"),
    ],
    "8.材质证明书": [
        (r"线材\正崴\PVC  MSDS.pdf", "线材 正崴 PVC MSDS"),
        (r"端子胶壳\联和\PA66 A3RV0 MSDS.pdf", "胶壳 PA66 MSDS"),
        (r"端子胶壳\联和\磷铜端子MSDS.pdf", "端子 磷铜 MSDS"),
        (r"套管\环保热缩套管物料安全资料MSDS.pdf", "套管 MSDS"),
        (r"锡丝\07CU物質安全資料表无铅锡线 Material Safe Data Sheet(1).pdf", "锡 MSDS"),
    ],
    "9.UL 证明": [
        (r"线材\正崴\E326510正崴UL证书2024.pdf", "线材 正崴 UL E326510"),
        (r"端子胶壳\联和\联和 E364711-UL1977.pdf", "端子胶壳 联和 UL E364711"),
        (r"套管\E352366 UL认证.pdf", "套管 UL E352366"),
    ],
}


@contextmanager
def com_session():
    pythoncom.CoInitialize()
    xl = w.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    for a in ("AskToUpdateLinks", "Interactive"):
        try:
            setattr(xl, a, False)
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


def make_icon(pdf, out_png, dpi=110):
    d = fitz.open(pdf)
    d[0].get_pixmap(dpi=dpi).save(out_png)
    d.close()
    return out_png


def resolve(p):
    return p if os.path.isabs(p) else os.path.join(LIB, p)


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    t0 = time.time()
    n = 0
    with com_session() as xl:
        wb = xl.Workbooks.Open(BASE)
        sheets = {ws.Name: ws for ws in wb.Worksheets}
        for prefix, files in MAP.items():
            ws = next((s for nm, s in sheets.items() if nm.startswith(prefix)), None)
            if ws is None:
                print(f"  ⚠ 找不到 sheet: {prefix}")
                continue
            left = 20
            for i, (rel, label) in enumerate(files):
                src = resolve(rel)
                if not os.path.exists(src):
                    print(f"  ⚠ 缺文件: {src}")
                    continue
                icon = make_icon(src, os.path.join(ICONDIR, f"{prefix[:2]}_{i}.png"))
                ws.OLEObjects().Add(ClassType="Package", Filename=src, Link=False,
                                    DisplayAsIcon=True, IconFileName=icon, IconIndex=0,
                                    Left=left, Top=175, Width=150, Height=195)
                left += 165
                n += 1
            print(f"  [{ws.Name}] 嵌入 {len(files)} 件")
        wb.SaveAs(OUT, FileFormat=51)
        wb.Close(SaveChanges=False)
    emb = len([x for x in zipfile.ZipFile(OUT).namelist() if "embeddings/oleObject" in x])
    print(f"\n✅ 全装配完成：嵌入 {n} 件，用时 {time.time()-t0:.1f}s，embeddings={emb}\n   -> {OUT}")


if __name__ == "__main__":
    main()
