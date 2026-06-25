# -*- coding: utf-8 -*-
"""W7 样品照片（第4标签页『4.样品照片（多角度）』）：照片数驱动的 Excel 布局。

照片来源=前端 UI 用户手动上传（微信收图→剪贴板→粘贴，UI 保留该习惯），**不在 Excel 里标红**。
本模块只负责：给定 N 张已上传照片(2-4) → 按对应布局摆进 Excel。段一 openpyxl。
布局实证 golden：2 张并排一行；3 张=2+1(末张居中)；4 张=2+2。col B 宽列内用 colOff 定位。

⏸ 挂起优化（潜在升级点，全套手测若有排版问题再执行）：
   当前用统一 4×5cm 槽，**未考虑照片尺寸/宽高比不一**。客户反映实际常是「2小1长」「3小一长」
   ——有"长"照(细长条，如整线展开照)+"小"照(方形细节照)。优化方向：按每张实际宽高比 + 长/小
   分类自适应（长照占满宽一行、小照并排），而非等尺寸槽。状态：挂起。
"""
from openpyxl.drawing.image import Image
from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
from openpyxl.drawing.xdr import XDRPositiveSize2D

SHEET = "4.样品照片（多角度）"
EMU_CM = 360000                      # 1cm = 360000 EMU
COL_B = 1                            # 宽内容列
X_PAIR = [4.3, 8.5]                  # 一行两张的 colOff(cm)
X_CENTER = 6.4                       # 单张居中 colOff(cm)
Y_ROWS = [11, 17, 23]               # 每行起始 row(0-indexed anchor)
Y_OFF = 0.5                          # rowOff(cm)
PHOTO_W, PHOTO_H = 4.0, 5.0          # 单张尺寸(cm)


def _cm(x):
    return int(round(x * EMU_CM))


def _anchor_col(im):
    return getattr(getattr(getattr(im, "anchor", None), "_from", None), "col", 0)


def photo_layout(n):
    """N 张照片(2-4)的位置 [(col, colOff_cm, row, rowOff_cm)]。2/行, 奇数末张居中。"""
    pos = []
    full, rem = divmod(n, 2)
    for r in range(full):
        for x in X_PAIR:
            pos.append((COL_B, x, Y_ROWS[r], Y_OFF))
    if rem:
        pos.append((COL_B, X_CENTER, Y_ROWS[full], Y_OFF))
    return pos


def fill_sample_photo(ws, photo_paths):
    """清 golden 残留成品照(留 LOGO) + 按张数布局摆入 N 张上传照。返回放入张数。"""
    ws._images = [im for im in ws._images if _anchor_col(im) == 0]   # 留 col0 LOGO
    layout = photo_layout(len(photo_paths))
    for path, (col, xoff, row, yoff) in zip(photo_paths, layout):
        img = Image(path)
        img.width, img.height = None, None    # 由 ext 定尺寸
        marker = AnchorMarker(col=col, colOff=_cm(xoff), row=row, rowOff=_cm(yoff))
        img.anchor = OneCellAnchor(_from=marker, ext=XDRPositiveSize2D(_cm(PHOTO_W), _cm(PHOTO_H)))
        ws.add_image(img)
    return len(layout)


def selfcheck_sample_photo(ws, n_expected):
    errs = []
    logos = [im for im in ws._images if _anchor_col(im) == 0]
    photos = [im for im in ws._images if _anchor_col(im) != 0]
    if not logos:
        errs.append("LOGO 被误删")
    if len(photos) != n_expected:
        errs.append(f"成品照数 {len(photos)}，应 {n_expected}")
    # 不重叠（同行两张 X 间距 ≥ 照片宽）
    if X_PAIR[1] - X_PAIR[0] < PHOTO_W:
        errs.append("同行两张会重叠")
    return errs
