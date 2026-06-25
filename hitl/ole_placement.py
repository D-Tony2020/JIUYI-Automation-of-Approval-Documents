# -*- coding: utf-8 -*-
"""OLE 落点计算(放置逻辑) — 从 run_m21 脚本抽出成可测/可复用模块。

纯函数, 不碰 COM。决定"每个 OLE 进哪个证据列、落哪个零件行"。
配套行为单测见 tests/test_ole_placement.py。
"""
from hitl.material_table import OLE_COL, compute_layout, DATA_TOP  # {MSDS:11(K),REACH:12(L),RoHS:25(Y)}
from study.embed_structure import MATCERT_PART_TOPS


def ev_col(name):
    """文件名 → 材质表证据列。ROHS→Y(25), REACH/SVHC→L(12), 余(MSDS等)→K(11)。"""
    up = name.upper()
    if "ROHS" in up:
        return OLE_COL["RoHS"]
    if "REACH" in up or "SVHC" in up:
        return OLE_COL["REACH"]
    return OLE_COL["MSDS"]


def part_top(name):
    """零件 → 材质证明书该零件行的 Top。按**零件类型**(非序号)对齐标签行,
    使产品用零件子集时(如只有线材+锡)锡仍落到锡的类型行, 与标签对齐。"""
    i = (3 if "锡" in name else
         2 if any(k in name for k in ("套", "热缩", "管")) else
         1 if any(k in name for k in ("胶", "端子")) else 0)
    return MATCERT_PART_TOPS[i] if i < len(MATCERT_PART_TOPS) else MATCERT_PART_TOPS[-1]


def mat_anchors_nocrutch(bom, mt_specs, start_row=DATA_TOP):
    """材质表 OLE 内容驱动落位 [(row, col)]:每份证据落其料的首块首行×证据列(K/L/Y);
    同(行,列)多份则块内顺延行。无 golden 拐杖, 料行由 compute_layout(bom) 结构算出。"""
    layout = compute_layout(bom, start_row)
    mat_first = [M["blocks"][0]["first"] if M["blocks"] else M["first"]
                 for P in layout["parts"] for M in P["materials"]]
    used, res = {}, []
    for s in mt_specs:
        mi = s.get("mat_idx")
        row0 = mat_first[mi] if (mi is not None and mi < len(mat_first)) else (mat_first[0] if mat_first else start_row)
        col = s["col"]
        rr = row0 + used.get((row0, col), 0)
        used[(row0, col)] = used.get((row0, col), 0) + 1
        res.append((rr, col))
    return res
