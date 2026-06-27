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
from hitl.file_account import _norm
from study.embed_structure import (GRID, grid_anchors, matcert_anchors,
                                   MATCERT_W, MATCERT_H, count_from_bom)

# 证据类型 → 材质表证据列(与 OLE_COL/ev_col 同口径): MSDS→K, REACH/SVHC→L, RoHS→Y, 其他→K
TYPE_COL = {"MSDS": OLE_COL["MSDS"], "REACH": OLE_COL["REACH"], "SVHC": OLE_COL["REACH"],
            "RoHS": OLE_COL["RoHS"], "其他": OLE_COL["MSDS"]}
_TYPE_ORDER = ("MSDS", "RoHS", "REACH", "SVHC", "其他")

# 单 OLE 表固定模板位(取自 golden, 各案近恒定; 同 run_m21.DEFAULT_ANCHOR)
DEFAULT_ANCHOR = {"图纸": (183, 266, 152, 42), "包装": (208, 271, 112, 60), "出货": (193, 261, 159, 42)}
DRAWING_W, DRAWING_H = 200, 130          # 图纸OLE尺寸(原硬编码320×220过大占大半页, 缩到~37%页宽·3:2适配横版图)
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


def stage2_to_nested_bom(materials, part_order=None):
    """stage2 扁平 materials → (nested_bom, ordered)。

    nested_bom = inject_data/compute_layout 吃的嵌套格(零件→材质→单报告块)。
    ordered = 按"零件序 × 零件内 stage2 序"展开的 stage2 材质列表——其下标即 mat_idx,
             与 compute_layout(nested) 的展开序逐一对齐(放置不落错行的根)。
    part_order: 零件展示顺序(持久化拖动序); 给则零件按它排(项次跟随), 否则零件首现序。
    """
    parts, src, order = {}, {}, []
    for m in materials:
        if m.get("豁免"):                       # 豁免(重复合并/特殊)不进材质表+不嵌OLE(前端用户流跟进)
            continue
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
    if part_order is None:                              # 默认读全局持久化零件顺序(下游自动跟随)
        try:
            from hitl import dicts
            part_order = dicts.part_order()
        except Exception:
            part_order = []
    if part_order:
        idx = {p: i for i, p in enumerate(part_order)}
        order.sort(key=lambda p: (idx.get(p, len(part_order)),))   # 持久化序在前, 序外保首现序(稳定)
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
    excluded = {_norm(e.get("文件") if isinstance(e, dict) else e)
                for e in (stage2_bom.get("excluded_files") or [])}   # 本单不收录, 不嵌
    nested, ordered = stage2_to_nested_bom(materials)
    sheet_names = stage2_bom.get("_sheet_names") or []
    mt_sheet = _find_sheet(sheet_names, "材质表")
    cert_sheet = _find_sheet(sheet_names, "材质证明")

    partcat = _part_category(materials)          # 零件→部件类别标签(线材/胶座端子/套管)
    specs, mt_specs = [], []
    seen_mt = set()
    for mi, m in enumerate(ordered):
        名 = (m.get("材质") or "").strip()
        for typ in _TYPE_ORDER:
            col = TYPE_COL[typ]
            for fn in _mat_files(m, typ):
                if _norm(os.path.basename(fn)) in excluded:
                    continue
                key = (mi, col, os.path.basename(fn))   # 同材质同列同文件去重(防 REACH+SVHC 同名双挂→2个重叠OLE)
                if key in seen_mt:
                    continue
                seen_mt.add(key)
                sp = {"sheet": mt_sheet, "pdf": os.path.join(materials_dir, fn), "short": "材质表",
                      "mat_idx": mi, "col": col, "W": 56, "H": 42, "label": f"{名} {typ}".strip()}
                mt_specs.append(sp)
                specs.append(sp)
    for sp, (r, c) in zip(mt_specs, mat_anchors_nocrutch(nested, mt_specs)):
        sp["row"], sp["col"] = r, c

    cert_pos = matcert_anchors(nested)           # [(L,T)] 按零件分组横排, 序 == ordered
    seen_part = set()
    for mi, m in enumerate(ordered):
        msds = _mat_files(m, "MSDS")
        if not msds or mi >= len(cert_pos):
            continue
        if _norm(os.path.basename(msds[0])) in excluded:
            continue
        L, T = cert_pos[mi]
        零件 = (m.get("零件") or "").strip()
        bj = partcat.get(零件, "") if (零件 and 零件 not in seen_part) else ""   # 每零件组首张标部件类别(线材/胶座端子/套管, 如golden)
        if 零件:
            seen_part.add(零件)
        specs.append({"sheet": cert_sheet, "pdf": os.path.join(materials_dir, msds[0]),
                      "short": "材质证明", "L": L, "T": T, "W": MATCERT_W, "H": MATCERT_H,
                      "label": (m.get("材质") or "").strip(), "部件标签": bj})
    return specs, nested, ordered


def _part_category(materials):
    """每零件的部件类别标签(OLE 下方显, 如golden 线材/端子/套管) = 该零件各材质的材质类别去重保序拼接。
    导线(全线材)→线材; 胶座端子(胶座+端子)→胶座端子; 热缩管(套管)→套管。
    """
    cat = {}
    for m in materials:
        if m.get("豁免"):
            continue
        p = (m.get("零件") or "").strip()
        c = (m.get("材质类别") or "").strip()
        if p and c:
            cat.setdefault(p, [])
            if c not in cat[p]:
                cat[p].append(c)
    return {p: "".join(cs) for p, cs in cat.items()}


def _infer_part(base, materials):
    """单报告→零件: 学习字典优先(成长型, 解型号码1061/盐雾) → file_link 内容/颜色匹配兜底。"""
    if not materials:
        return ""
    try:                                            # 学习字典(操作员历史确认)
        from hitl import dicts
        la = dicts.lookup_assign(base)
        if la.get("零件"):
            return la["零件"]
    except Exception:
        pass
    try:
        from hitl.file_link import suggest_for
        return ((suggest_for(base, "其他", materials)) or {}).get("零件", "")
    except Exception:
        return ""


def assign_parts_for(report_bases, materials, part_order):
    """一张横排表的报告 → {文件: 零件}: 先内容匹配能推断的, 余者补剩余采购部件(按零件序)。
    供 pile_specs 落标签/排序 + grid_reports 预填(④操作员归属选择的默认值)。
    """
    partcat = _part_category(materials or [])
    parts_seq = [p for p in (part_order or []) if p in partcat]
    out, used, pending = {}, set(), []
    for b in report_bases:
        p = _infer_part(b, materials)
        if p in partcat and p not in used:
            out[b] = p; used.add(p)
        else:
            pending.append(b)
    remaining = [p for p in parts_seq if p not in used]
    for b, p in zip(pending, remaining):
        out[b] = p
    for b in pending[len(remaining):]:
        out[b] = ""
    return out


def grid_reports(materials_dir, materials=None, part_order=None, part_assign=None, excluded=None):
    """横排表(部件承认/UL/信赖性)报告清单 + best-effort 建议零件(供④操作员归属选择, 默认预填)。
    → [{文件, 表, 建议零件}]。收集口径同 pile_specs: route() ∪ 部件归属手动指派(救route=∅), excluded 剔除。
    """
    part_assign = part_assign or {}
    exc = {_norm(x.get("文件") if isinstance(x, dict) else x) for x in (excluded or [])}
    by = {}
    for f in sorted(glob.glob(os.path.join(materials_dir, "*.pdf"))):
        base = os.path.basename(f)
        if _norm(base) in exc:
            continue
        shorts = {s for s in route(base) if s in ("部件承认", "UL", "信赖性")}
        man = _pa_slot(part_assign.get(base))
        if man in ("部件承认", "UL", "信赖性"):
            shorts.add(man)
        for short in shorts:
            by.setdefault(short, []).append(base)
    out = []
    for short, bases in by.items():
        auto = assign_parts_for(bases, materials, part_order)
        for b in bases:
            out.append({"文件": b, "表": short, "建议零件": _pa_part(part_assign.get(b)) or auto.get(b, "")})
    return out


def _pa_slot(v):
    return v.get("槽") if isinstance(v, dict) else None       # 部件归属值: {槽,零件}(新) 或 零件str(旧)


def _pa_part(v):
    return (v.get("零件") if isinstance(v, dict) else v) or ""


def pile_specs(materials_dir, sheet_names, drawing_pdf=None, materials=None, part_order=None,
               part_assign=None, excluded=None):
    """非材质级表(部件承认/UL/信赖性/包装/出货/图纸)specs: route() 建议 ∪ 操作员手动归位, GRID/固定位落。

    收集口径(零丢失): route() 命中 ∪ 部件归属手动指派的横排槽(救 route=∅ 的料号文件); excluded 一律剔除。
    横排零件归属: 操作员④选的 part_assign(支持 {槽,零件}/零件str) 优先, 否则 best-effort 自动分配。
    """
    part_assign = part_assign or {}
    excluded = {_norm(x.get("文件") if isinstance(x, dict) else x) for x in (excluded or [])}
    by_short = {k: [] for k in ("部件承认", "UL", "信赖性", "包装", "出货")}
    for f in sorted(glob.glob(os.path.join(materials_dir, "*.pdf"))):
        base = os.path.basename(f)
        if _norm(base) in excluded:                          # 本单不收录, 不放
            continue
        shorts = {s for s in route(base) if s in by_short}
        man = _pa_slot(part_assign.get(base))                # 操作员手动指派的横排槽(含 route=∅)
        if man in by_short:
            shorts.add(man)
        for short in shorts:
            fs = _find_sheet(sheet_names, short)
            if fs:
                by_short[short].append({"sheet": fs, "pdf": f, "short": short,
                                        "label": os.path.splitext(base)[0]})   # 标签=文件名核心(部件/零件名)
    partcat = _part_category(materials or [])                                     # 零件→部件类别标签(线材/胶座端子/套管)
    pidx = {p: i for i, p in enumerate(part_order or [])}
    part_assign = part_assign or {}
    specs = []
    for short, gk in (("部件承认", "部件承认书"), ("UL", "UL证明"), ("信赖性", "信赖性")):
        bases = [os.path.basename(sp["pdf"]) for sp in by_short[short]]
        auto = assign_parts_for(bases, materials, part_order)
        for sp in by_short[short]:
            b = os.path.basename(sp["pdf"])
            零件 = (_pa_part(part_assign.get(b)) or auto.get(b, "")).strip()      # ④操作员选的优先(支持{槽,零件}/零件str)
            sp["部件标签"] = partcat.get(零件, "")                                 # OLE 下方部件类别标签
            sp["_零件"] = 零件
        ordered = sorted(by_short[short], key=lambda sp: pidx.get(sp.get("_零件", ""), len(pidx) + 1))
        g = GRID[gk]
        for sp, (L, T) in zip(ordered, grid_anchors(len(ordered), **g)):
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
                          "L": L, "T": T, "W": DRAWING_W, "H": DRAWING_H, "label": "图纸"})
    return specs


def build_specs(stage2_bom, sheet_names, materials_dir, drawing_pdf=None):
    """全部 OLE specs(材质表+材质证明 由链驱动, 其余按 route 路由)。不生 icon(留装配时)。"""
    s2 = dict(stage2_bom, _sheet_names=sheet_names)
    specs, nested, ordered = material_specs(s2, materials_dir)
    part_order = [p["零件"] for p in nested]                       # 装表零件序(横排pile跟随, 与材质表同序)
    specs += pile_specs(materials_dir, sheet_names, drawing_pdf,
                        materials=stage2_bom.get("materials", []), part_order=part_order,
                        part_assign=stage2_bom.get("部件归属"),       # ④操作员选的横排报告零件归属(含route=∅手动指派)
                        excluded=stage2_bom.get("excluded_files"))   # 本单不收录, 不嵌
    return specs, nested, ordered


def expected_slots(nested_bom):
    """各表应有 OLE 槽数(空槽提示用): count_from_bom + 材质表=证据文件数另算。"""
    return count_from_bom(nested_bom)
