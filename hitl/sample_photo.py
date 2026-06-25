# -*- coding: utf-8 -*-
"""W7 样品照片：保留原图宽高比的动态布局（只缩放不变形）。

照片来源=前端 UI 用户手动上传（微信收图→剪贴板→粘贴）。本模块给定 N 张已上传照 → 摆进 Excel。
实证 7 案规律：「小」照=竖图(宽高比0.6-0.8,细节)，「长」照=横图(宽高比1.1-4.0,整体)。
布局：竖照同高侧排在上排；横照满宽(限框内)堆叠在下方。**每张按原始宽高比定尺寸，绝不压扁。**
"""
import io as _io

from openpyxl.drawing.image import Image
from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
from openpyxl.drawing.xdr import XDRPositiveSize2D
from PIL import Image as PILImage

SHEET = "4.样品照片（多角度）"
EMU_CM = 360000
COL_B = 1                 # 宽内容列
TOP_ROW = 11              # 竖照(小)锚定行(0-indexed) → 上排
LONG_ROW = 17             # 横照(长)锚定行(0-indexed) → 下排(各自的行, 不靠大rowOff避免WPS截断)
X0 = 3.0                  # 首张 colOff(cm)
GAP = 0.4                 # 间距(cm)
ROWOFF = 0.3              # 行内 rowOff(cm)
ASPECT_SPLIT = 1.0        # <1 竖(小) / ≥1 横(长)
H_PORTRAIT = 5.0          # 竖照统一高(cm)，宽=高×宽高比
LAND_WMAX, LAND_HMAX = 9.0, 5.0    # 横照限框(cm)；宽 0.7×原13≈9(老板要求缩小)
ROW_CM = 0.99             # 行高约 28pt ≈ 0.99cm(多横照换行用)


def _cm(x):
    return int(round(x * EMU_CM))


def _anchor_col(im):
    return getattr(getattr(getattr(im, "anchor", None), "_from", None), "col", 0)


def _aspect(path):
    try:
        w, h = PILImage.open(path).size
        return w / h if h else 0.7
    except Exception:
        return 0.7


def _place(ws, path, x_cm, from_row, y_cm, w_cm, h_cm):
    img = Image(path)
    marker = AnchorMarker(col=COL_B, colOff=_cm(x_cm), row=from_row, rowOff=_cm(y_cm))
    img.anchor = OneCellAnchor(_from=marker, ext=XDRPositiveSize2D(_cm(w_cm), _cm(h_cm)))
    ws.add_image(img)
    return (w_cm, h_cm)


def plan_layout(aspects):
    """各照宽高比 → [(x_cm, from_row, rowOff_cm, w_cm, h_cm)]，保比例。竖照上排侧排、横照下排满宽。"""
    out = [None] * len(aspects)
    idx_p = [i for i, a in enumerate(aspects) if a < ASPECT_SPLIT]   # 竖/小 → 上排
    idx_l = [i for i, a in enumerate(aspects) if a >= ASPECT_SPLIT]  # 横/长 → 下排
    x = X0
    for i in idx_p:
        w = H_PORTRAIT * aspects[i]
        out[i] = (x, TOP_ROW, ROWOFF, w, H_PORTRAIT)
        x += w + GAP
    row = LONG_ROW
    for i in idx_l:
        a = aspects[i]
        w, h = LAND_WMAX, LAND_WMAX / a
        if h > LAND_HMAX:
            h, w = LAND_HMAX, LAND_HMAX * a
        out[i] = (X0, row, ROWOFF, w, h)
        row += int(h / ROW_CM) + 1      # 多横照各占自己的行带, 往下堆叠
    return out


def fill_sample_photo(ws, photo_paths):
    """清 golden 残照(留LOGO) + 按原图比例动态摆 N 张上传照(只缩放不变形)。返回张数。"""
    ws._images = [im for im in ws._images if _anchor_col(im) == 0]
    aspects = [_aspect(p) for p in photo_paths]
    for path, (x, r, y, w, h) in zip(photo_paths, plan_layout(aspects)):
        _place(ws, path, x, r, y, w, h)
    return len(photo_paths)


def selfcheck_sample_photo(ws, n_expected):
    errs = []
    logos = [im for im in ws._images if _anchor_col(im) == 0]
    photos = [im for im in ws._images if _anchor_col(im) != 0]
    if not logos:
        errs.append("LOGO 被误删")
    if len(photos) != n_expected:
        errs.append(f"成品照数 {len(photos)}，应 {n_expected}")
    # 比例保真：每张 ext 宽高比 ≈ 原图宽高比
    for im in photos:
        ext = im.anchor.ext
        placed = (ext.width / ext.height) if ext.height else 0
        native = _aspect_from_image(im)
        if native and abs(placed - native) / native > 0.05:
            errs.append(f"照片变形：摆放比{round(placed,2)} vs 原图比{round(native,2)}")
            break
    return errs


def _aspect_from_image(im):
    try:
        return _aspect_bytes(im._data())
    except Exception:
        return None


def _aspect_bytes(data):
    w, h = PILImage.open(_io.BytesIO(data)).size
    return w / h if h else None
