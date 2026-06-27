# -*- coding: utf-8 -*-
"""覆盖审计(单一真相): 红线"每个上传文件都有主"——全集 = 已放置 ∪ 待归位 ∪ 显式排除。

被 bom_confirm / filetree_state / validate_filetree / 导出预检 复用, "剩余"定义全栈一致。
route() 只作"建议器/固定位命中判据", 不作"存在性判据"(否则 route=∅ 文件静默丢)。
红线: 材质豁免只免 BOM 行, 其文件不算已放置→落待归位(操作员重挂到非豁免同名材质), 见 [[jiuyi-exempt-not-drop-files]]。
口径: 按 _norm(basename) 去空格去大小写归一, 扇出(MSDS→材质表+材质证明)仍算 1 份 placed。
"""
import glob
import os
import re

from hitl.file_router import route

_FILE_KEYS = ("MSDS", "RoHS", "REACH", "SVHC", "其他")
_GRID_FIXED = {"部件承认", "UL", "信赖性", "包装", "出货"}   # pile_specs 实际从料堆放这些; 图纸只走 drawing_pdf, 不在此


def _norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def _files_of(m):
    out = []
    for k in _FILE_KEYS:
        v = (m.get("files") or {}).get(k)
        if isinstance(v, str):
            if v:
                out.append(v)
        else:
            out.extend(x for x in (v or []) if x)
    return out


def account_files(materials_dir, materials, 部件归属=None, excluded_files=None, drawing_pdf=None):
    """→ {placed:set, pending:list, excluded:list, total:int}, 三者按 _norm(basename) 两两不相交且并==全集。

    placed = 非豁免材质 files 桶 ∪ route 命中(部件承认/UL/信赖性/包装/出货) ∪ 部件归属手动指派 ∪ 图纸basename。
    pending = 全集 − placed − excluded (含 route=∅、材质级认不准、豁免材质的文件)。
    """
    部件归属 = 部件归属 or {}
    excluded_set = set()
    for e in (excluded_files or []):
        nm = e.get("文件") if isinstance(e, dict) else e
        if nm:
            excluded_set.add(_norm(nm))

    norm2real = {}                                           # 归一名→磁盘真实名(返回真实名供UI/匹配)
    for f in glob.glob(os.path.join(materials_dir, "*.pdf")):
        b = os.path.basename(f)
        norm2real[_norm(b)] = b
    total = set(norm2real)

    placed = set()
    for m in (materials or []):
        if m.get("豁免"):                                    # 红线: 豁免材质文件不算已放置→落 pending
            continue
        for fn in _files_of(m):
            placed.add(_norm(os.path.basename(fn)))
    for n, b in norm2real.items():
        if route(b) & _GRID_FIXED:                           # route 命中横排/固定位 = 已放置
            placed.add(n)
    for fn in 部件归属.keys():                                # 操作员手动指派到横排槽的(含 route=∅)
        placed.add(_norm(os.path.basename(fn)))
    if drawing_pdf:
        placed.add(_norm(os.path.basename(drawing_pdf)))     # 图纸单独传入, 不在 materials/

    placed &= total                                          # 只算确实在料堆里的
    excluded = excluded_set & total
    placed -= excluded
    pending = total - placed - excluded
    assert len(placed) + len(pending) + len(excluded) == len(total), "覆盖不变式破: 已放置+待归位+排除 ≠ 全集"
    real = lambda ns: sorted(norm2real[n] for n in ns)
    return {"placed": real(placed), "pending": real(pending), "excluded": real(excluded), "total": len(total)}
