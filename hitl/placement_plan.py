# -*- coding: utf-8 -*-
"""M2.4 放置引擎: stage2_bom 文件↔材质链 → OLE embed specs。零 COM、纯位置计算。

复用 M2.1 放置原语(run_m21 同款), 只把驱动源从 golden+content_match 换成 stage2_bom:
- 材质表: 每材质每证据文件 → (mat_idx, 证据列K/L/Y), 行由 mat_anchors_nocrutch(compute_layout) 算。
- 材质证明书: 每材质 MSDS 一份 → matcert_anchors(nested) 按零件分组横排。
- 部件承认/UL/信赖性/包装/出货/图纸: 这些非材质级文件不在 file_link 链里, 按 route() 重路由料堆,
  GRID/DEFAULT_ANCHOR 落位(同 run_m21)。

最高不变式: 段一填格(fill_material_table)与段二放置(本模块)必须吃同一 nested_bom——
compute_layout(nested) 既定材质表行结构、又定 OLE 落点行, ordered 序 == 展开序保证 mat_idx 对齐。
"""
import glob
import os

from hitl.material_table import OLE_COL
from hitl.ole_placement import mat_anchors_nocrutch
from hitl.file_router import route
from study.embed_structure import (GRID, grid_anchors, matcert_anchors,
                                   MATCERT_W, MATCERT_H, count_from_bom)

# 证据类型 → 材质表证据列(与 OLE_COL/ev_col 同口径): MSDS→K, REACH/SVHC→L, RoHS→Y, 其他→K
TYPE_COL = {"MSDS": OLE_COL["MSDS"], "REACH": OLE_COL["REACH"], "SVHC": OLE_COL["REACH"],
            "RoHS": OLE_COL["RoHS"], "其他": OLE_COL["MSDS"]}
_TYPE_ORDER = ("MSDS", "RoHS", "REACH", "SVHC", "其他")

# 单 OLE 表固定模板位(取自 golden, 各案近恒定; 同 run_m21.DEFAULT_ANCHOR)
DEFAULT_ANCHOR = {"图纸": (183, 266, 152, 42), "包装": (208, 271, 112, 60), "出货": (193, 261, 159, 42)}
# 短名 → GRID 键(网格类表)
_GRID_KEY = {"部件承认": "部件承认书", "UL": "UL证明", "信赖性": "信赖性"}
_SHORT_KW = {"材质表": "材质成分", "材质证明": "材质证明", "部件承认": "部件",
             "UL": "UL", "信赖性": "信赖", "包装": "包装", "出货": "出货", "图纸": "图纸"}


def _find_sheet(sheet_names, short):
    """按短名关键词在实际 sheet 名里找(模板表名带序号/空格, route 用短名)。"""
    kw = _SHORT_KW[short]
    for n in sheet_names:
        if kw in n or (short == "出货" and ("出貨" in n or "检验" in n)):
            return n
    return None


def stage2_to_nested_bom(materials):
    """stage2 扁平 materials → (nested_bom, ordered)。

    nested_bom = inject_data/compute_layout 吃的嵌套格(零件→材质→单报告块)。
    ordered = 按"零件首现序 × 零件内 stage2 序"展开的 stage2 材质列表——其下标即 mat_idx,
             与 compute_layout(nested) 的展开序逐一对齐(放置不落错行的根)。
    一材一块(stage2 一 MSDS 一材质); 材质类别零件级合并(首材质写余空, 同 to_inject_bom)。
    """
    parts, src, order = {}, {}, []
    for m in materials:
        p = (m.get("零件") or "").strip()
        if p not in parts:
            parts[p] = {"零件": p, "供应商": (m.get("供应商") or "").strip(),
                        "材质类别": (m.get("材质类别") or "").strip(), "materials": []}
            src[p] = []
            order.append(p)
        parts[p]["materials"].append({
            "材质类别": m.get("材质类别", ""),       # 不坍缩: 每材质保自己的类别(D列由 inject_data 按类别组合并)
            "材质": m.get("材质", ""),
            "blocks": [{"成份": m.get("成份", []), "RoHS": m.get("RoHS", {}),
                        "报告编号": m.get("报告编号", ""), "报告日期": m.get("报告日期", "")}],
        })
        src[p].append(m)
    nested = [parts[p] for p in order]
    ordered = [m for p in order for m in src[p]]
    return nested, ordered


def _mat_files(m, typ):
    """材质 m 的某证据类型文件列表(MSDS 是单值, 余是列表)。"""
    fz = m.get("files") or {}
    v = fz.get(typ)
    if v is None:
        return []
    return [v] if isinstance(v, str) else list(v)


def material_specs(stage2_bom, materials_dir):
    """材质表 + 材质证明书 specs(由文件↔材质链驱动, 纯位置, 不生 icon)。

    材质表: 每材质每证据文件 → spec{row,col}(结构驱动); 材质证明: 每材质 MSDS 一份 → spec{L,T}。
    返回 (specs, nested_bom, ordered)。
    """
    materials = stage2_bom.get("materials", [])
    nested, ordered = stage2_to_nested_bom(materials)
    sheet_names = stage2_bom.get("_sheet_names") or []
    mt_sheet = _find_sheet(sheet_names, "材质表")
    cert_sheet = _find_sheet(sheet_names, "材质证明")

    specs, mt_specs = [], []
    for mi, m in enumerate(ordered):
        for typ in _TYPE_ORDER:
            col = TYPE_COL[typ]
            for fn in _mat_files(m, typ):
                sp = {"sheet": mt_sheet, "pdf": os.path.join(materials_dir, fn), "short": "材质表",
                      "mat_idx": mi, "col": col, "W": 56, "H": 42}
                mt_specs.append(sp)
                specs.append(sp)
    for sp, (r, c) in zip(mt_specs, mat_anchors_nocrutch(nested, mt_specs)):
        sp["row"], sp["col"] = r, c

    cert_pos = matcert_anchors(nested)           # [(L,T)] 按零件分组横排, 序 == ordered
    for mi, m in enumerate(ordered):
        msds = _mat_files(m, "MSDS")
        if not msds or mi >= len(cert_pos):
            continue
        L, T = cert_pos[mi]
        specs.append({"sheet": cert_sheet, "pdf": os.path.join(materials_dir, msds[0]),
                      "short": "材质证明", "L": L, "T": T, "W": MATCERT_W, "H": MATCERT_H})
    return specs, nested, ordered


def pile_specs(materials_dir, sheet_names, drawing_pdf=None):
    """非材质级表(部件承认/UL/信赖性/包装/出货/图纸)specs: 按 route() 重路由料堆, GRID/固定位落。

    这些文件不在 file_link 材质链里(link 只管材质表/材质证明), 故从料堆按文件名关键词路由。
    """
    by_short = {k: [] for k in ("部件承认", "UL", "信赖性", "包装", "出货")}
    for f in sorted(glob.glob(os.path.join(materials_dir, "*.pdf"))):
        base = os.path.basename(f)
        for short in route(base):
            if short in by_short:
                fs = _find_sheet(sheet_names, short)
                if fs:
                    by_short[short].append({"sheet": fs, "pdf": f, "short": short})
    specs = []
    for short, gk in (("部件承认", "部件承认书"), ("UL", "UL证明"), ("信赖性", "信赖性")):
        g = GRID[gk]
        for sp, (L, T) in zip(by_short[short], grid_anchors(len(by_short[short]), **g)):
            sp.update(L=L, T=T, W=g["w"], H=g["h"])
            specs.append(sp)
    for short in ("包装", "出货"):
        L, T, W, H = DEFAULT_ANCHOR[short]
        for sp in by_short[short]:
            sp.update(L=L, T=T, W=W, H=H)
            specs.append(sp)
    if drawing_pdf:
        fs = _find_sheet(sheet_names, "图纸")
        L, T, W, H = DEFAULT_ANCHOR["图纸"]
        if fs:
            specs.append({"sheet": fs, "pdf": drawing_pdf, "short": "图纸",
                          "L": L, "T": T, "W": 320, "H": 220})
    return specs


def build_specs(stage2_bom, sheet_names, materials_dir, drawing_pdf=None):
    """全部 OLE specs(材质表+材质证明 由链驱动, 其余按 route 路由)。不生 icon(留装配时)。"""
    s2 = dict(stage2_bom, _sheet_names=sheet_names)
    specs, nested, ordered = material_specs(s2, materials_dir)
    specs += pile_specs(materials_dir, sheet_names, drawing_pdf)
    return specs, nested, ordered


def expected_slots(nested_bom):
    """各表应有 OLE 槽数(空槽提示用): count_from_bom + 材质表=证据文件数另算。"""
    return count_from_bom(nested_bom)
