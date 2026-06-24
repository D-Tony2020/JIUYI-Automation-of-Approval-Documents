# -*- coding: utf-8 -*-
"""段二 COM：把源文件嵌入承认书表为可双击 OLE + PNG 预览（复用 spike 已验证方案）。

约束：OLE 只能 COM 嵌；嵌后该本不可再用 openpyxl 保存（会丢 OLE）。故本模块是
两段式的"段二"，永远在 openpyxl 填格（build_upto）之后、作为终态。
"""
import os
import zipfile
from contextlib import contextmanager

import pythoncom
import win32com.client as win32
import fitz

# 电子表格 COM 引擎 ProgID 优先级。客户机=WPS，故优先 WPS 自家 KET.Application；
# 回退 Excel.Application（注：装了 WPS 的机器上 Excel.Application 常被 WPS 劫持，
# 二者都指向 WPS——本机实测即如此）。引擎可换、代码不变（WPS COM 兼容 Excel 对象模型）。
COM_PROGIDS = ["KET.Application", "Excel.Application"]


@contextmanager
def com_session(progids=None):
    """无头电子表格会话（WPS/Excel 通用）：四必设 + 退出强杀，防僵尸进程。

    依次尝试 progids，绑定第一个可用引擎；xl._bound 记录 (progid, name, ver, path)。
    """
    progids = progids or COM_PROGIDS
    pythoncom.CoInitialize()
    xl = None
    bound = None
    for pid in progids:
        try:
            xl = win32.DispatchEx(pid)
            bound = pid
            break
        except Exception:
            continue
    if xl is None:
        pythoncom.CoUninitialize()
        raise RuntimeError(f"无可用电子表格 COM 引擎（尝试过 {progids}）")
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


def engine_info(progids=None):
    """探测实际绑定的电子表格引擎（部署 precheck 用）：返回 dict 含 progid/name/version/path/is_wps。"""
    progids = progids or COM_PROGIDS
    pythoncom.CoInitialize()
    bound = name = ver = path = None
    try:
        xl = None
        for pid in progids:
            try:
                xl = win32.DispatchEx(pid)
                bound = pid
                break
            except Exception:
                continue
        if xl is None:
            raise RuntimeError(f"无可用电子表格 COM 引擎（尝试过 {progids}）")
        try:
            name, ver, path = xl.Name, xl.Version, xl.Path
        finally:
            try:
                xl.Quit()
            except Exception:
                pass
    finally:
        pythoncom.CoUninitialize()
    is_wps = bool(path) and ("wps" in path.lower() or "kingsoft" in path.lower())
    return {"progid": bound, "name": name, "version": ver, "path": path, "is_wps": is_wps}


def extract_embedded_pdf(xlsx_path, ole_basename, out_pdf):
    """从 xlsx 的某个 oleObject*.bin 抽出内嵌 PDF（demo 取 golden 图纸用）。"""
    with zipfile.ZipFile(xlsx_path) as z:
        data = z.read(f"xl/embeddings/{ole_basename}")
    s = data.find(b"%PDF")
    e = data.rfind(b"%%EOF")   # 取最后一个 %%EOF(PDF 增量更新有多个), 避免截断损坏
    if s < 0 or e < 0 or e < s:
        raise ValueError(f"{ole_basename} 内未找到完整 PDF")
    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
    with open(out_pdf, "wb") as f:
        f.write(data[s:e + 5])
    return out_pdf


def _fallback_icon(out_png):
    """通用占位图标(源PDF空/损坏时用)，fitz 画一张, 不依赖 PIL。"""
    doc = fitz.open()
    page = doc.new_page(width=120, height=150)
    page.draw_rect(page.rect, color=(0.5, 0.5, 0.5), fill=(0.95, 0.95, 0.95))
    page.insert_text((28, 80), "PDF", fontsize=24, color=(0.6, 0, 0))
    page.get_pixmap(dpi=96).save(out_png)
    doc.close()


def make_icon(pdf, out_png, dpi=110):
    """渲染 PDF 首页为 PNG 预览。失败(空/损坏)则用通用占位图标, 不崩。返回 out_png。"""
    try:
        d = fitz.open(pdf)
        try:
            if d.page_count > 0:
                d[0].get_pixmap(dpi=dpi).save(out_png)
                return out_png
        finally:
            d.close()
    except Exception:
        pass
    _fallback_icon(out_png)
    return out_png


def _find_sheet(wb, name):
    for sh in wb.Worksheets:
        if sh.Name.strip() == name.strip():
            return sh
    raise ValueError(f"未找到表 {name}")


def embed_one(src_xlsx, out_xlsx, sheet_name, pdf, png, geo):
    """打开 src，在 sheet 嵌入 1 个 OLE(Package+图标)，另存 out。geo=(L,T,W,H)。

    注意：WPS 的 OLEObjects().Add() **忽略**传入的位置参数（会丢到左上角 0,0），
    必须 Add 之后在返回对象上**显式设** .Left/.Top/.Width/.Height（Excel/WPS 都认）。
    """
    left, top, width, height = geo
    with com_session() as xl:
        wb = xl.Workbooks.Open(os.path.abspath(src_xlsx))
        sh = _find_sheet(wb, sheet_name)
        obj = sh.OLEObjects().Add(ClassType="Package", Filename=os.path.abspath(pdf), Link=False,
                                  DisplayAsIcon=True, IconFileName=os.path.abspath(png), IconIndex=0)
        try:
            obj.ShapeRange.LockAspectRatio = 0  # 关宽高比锁定(否则设高时宽按图标比例反推放大)
        except Exception:
            pass
        obj.Left, obj.Top, obj.Width, obj.Height = left, top, width, height
        if os.path.exists(out_xlsx):
            os.remove(out_xlsx)
        wb.SaveAs(os.path.abspath(out_xlsx), FileFormat=51)
        wb.Close(SaveChanges=False)
    return out_xlsx


def embed_many(src_xlsx, out_xlsx, specs):
    """一个 COM 会话嵌入多个 OLE（段二总装）。specs=[{sheet,pdf,icon,L,T,W,H}, ...]。

    WPS 忽略 Add 位置参数 → Add 后显式设几何。整本 cell 填完后由此一次性嵌全部 OLE(终态)。
    """
    with com_session() as xl:
        wb = xl.Workbooks.Open(os.path.abspath(src_xlsx))
        sheet_cache = {}
        for spec in specs:
            nm = spec["sheet"]
            sh = sheet_cache.get(nm)
            if sh is None:
                sh = _find_sheet(wb, nm)
                sheet_cache[nm] = sh
            obj = sh.OLEObjects().Add(
                ClassType="Package", Filename=os.path.abspath(spec["pdf"]), Link=False,
                DisplayAsIcon=True, IconFileName=os.path.abspath(spec["icon"]), IconIndex=0)
            try:
                obj.ShapeRange.LockAspectRatio = 0  # 关宽高比锁定; 否则设高时宽按巨型图标比例反推放大→重叠
            except Exception:
                pass
            # 两种定位: 结构驱动(单元格行列→读该格Left/Top, 材质表用) / 绝对(L,T, 其他表用)
            if spec.get("row") and spec.get("col"):
                cell = sh.Cells(spec["row"], spec["col"])
                left, top = cell.Left + 2, cell.Top + 2  # 内缩2点, 避开边界取整(否则锚点算到前一格)
            else:
                left, top = spec["L"], spec["T"]
            obj.Left, obj.Top, obj.Width, obj.Height = left, top, spec["W"], spec["H"]
        if os.path.exists(out_xlsx):
            os.remove(out_xlsx)
        wb.SaveAs(os.path.abspath(out_xlsx), FileFormat=51)
        wb.Close(SaveChanges=False)
    return out_xlsx


def count_ole(xlsx_path):
    """zip 级整本 OLE 对象计数。"""
    with zipfile.ZipFile(xlsx_path) as z:
        return len([n for n in z.namelist() if "embeddings/oleObject" in n])


def verify_open(xlsx_path):
    """COM 复开：返回 {表名: OLE数, _total: n, _geo: {表名:(L,T,W,H)}}。需修复/打不开则抛错。"""
    res = {}
    geo = {}
    with com_session() as xl:
        wb = xl.Workbooks.Open(os.path.abspath(xlsx_path), UpdateLinks=0, ReadOnly=True)
        total = 0
        for sh in wb.Worksheets:
            try:
                c = sh.OLEObjects().Count
            except Exception:
                c = 0
            if c:
                res[sh.Name] = c
                total += c
                try:
                    o = sh.OLEObjects().Item(1)
                    geo[sh.Name] = (round(o.Left, 1), round(o.Top, 1),
                                    round(o.Width, 1), round(o.Height, 1))
                except Exception:
                    pass
        wb.Close(SaveChanges=False)
    res["_total"] = total
    res["_geo"] = geo
    return res
