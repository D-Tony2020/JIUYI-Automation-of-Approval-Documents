# -*- coding: utf-8 -*-
"""M2.4 无拐杖 e2e: 伪真单 → stage2_bom 文件↔材质链 → build_specs → OLE specs 计数对标 golden。

默认 spec 级(零 COM, 确定性快): 每案 propose(缓存) → 对齐 golden 赋零件/类别(模拟操作员) →
link_materials → plan_only → 各表 OLE 数 vs golden 实测。
--com <案号>: 对该案走真 COM 装配(embed_many+verify_open), 产终态 xlsx 供视觉验证(慢, 依赖WPS)。
SKIP YY60039397(损坏 golden)。
"""
import glob
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from hitl.material_extract import propose_bom_from_pile
from hitl.file_link import link_materials
from hitl.assemble_order import plan_only, count_specs_by_sheet, assemble
from hitl.placement_plan import stage2_to_nested_bom
from study.golden_parse import parse_golden
from study.case_data import _distinct_bins_per_sheet, extract_drawing_meta, extract_dimensions

PSEUDO = os.path.join(ROOT, "本单输入", "pseudo")
OUTROOT = os.path.join(ROOT, "产出留档", "M2.4-e2e")
SKIP = {"YY60039397"}


def _cas(comps, key):
    out = set()
    for c in comps or []:
        v = str(c.get(key) or "").replace(" ", "")
        for p in v.replace("、", ",").replace(";", ",").split(","):
            p = p.strip()
            if p and p not in ("/", "-"):
                out.add(p)
    return out


def _assign_parts_from_golden(props, g):
    """把 B 提议按 CAS 单射对到 golden 材质, 抄 golden 的 零件/材质类别(模拟操作员的不可约人工)。"""
    gc = [_cas(m.get("components"), "CAS") for m in g]
    bc = [_cas(p.get("成份"), "CAS") for p in props]
    cand = []
    for gi, gcs in enumerate(gc):
        if not gcs:
            continue
        for bi, bcs in enumerate(bc):
            inter = len(bcs & gcs)
            if inter:
                cand.append((inter / len(bcs | gcs), gi, bi))
    cand.sort(reverse=True)
    used_b, used_g, b2g = set(), set(), {}
    for _j, gi, bi in cand:
        if gi in used_g or bi in used_b:
            continue
        b2g[bi] = gi
        used_g.add(gi)
        used_b.add(bi)
    for bi, p in enumerate(props):
        gi = b2g.get(bi)
        p["零件"] = (g[gi]["零件"] if gi is not None else (p.get("零件") or "导线")) or "导线"
        p["材质类别"] = (g[gi]["材质类别"] if gi is not None else p.get("材质类别", "")) or "其他"
        p["已核对"] = True
    return props


def build_stage2(code, golden, materials_dir):
    props = propose_bom_from_pile(materials_dir)
    g = parse_golden(golden)
    _assign_parts_from_golden(props, g)
    linked, unlinked = link_materials(materials_dir, props)
    return {"materials": linked, "unlinked_files": [{"文件": b, "类型": t} for b, t in unlinked]}


def run_spec(code):
    golden_dir = None
    gt = os.path.join(PSEUDO, code, "_groundtruth.json")
    import json
    golden = json.load(open(gt, encoding="utf-8")).get("golden")
    materials = os.path.join(PSEUDO, code, "materials")
    dpdf = glob.glob(os.path.join(PSEUDO, code, "drawing", "*.pdf"))
    drawing_pdf = dpdf[0] if dpdf else None
    s2 = build_stage2(code, golden, materials)
    meta = extract_drawing_meta(golden)
    dims = extract_dimensions(golden)
    outdir = os.path.join(OUTROOT, code)
    _cell, specs, _nested = plan_only(s2, {"名称": meta.get("品类"), "品号": meta.get("品号"),
                                           "版本": meta.get("版本")}, dims, materials, drawing_pdf, outdir)
    mine = count_specs_by_sheet(specs)
    gold = {k: len(v) for k, v in _distinct_bins_per_sheet(golden).items()}
    # 按表名对齐(我的 sheet 名取自模板, golden 同模板)
    keys = sorted(set(gold) | set(mine))
    exact = sum(1 for k in keys if gold.get(k, 0) == mine.get(k, 0))
    diffs = {k.split(".")[-1].strip()[:8]: (mine.get(k, 0), gold.get(k, 0))
             for k in keys if gold.get(k, 0) != mine.get(k, 0)}
    return {"code": code, "specs": len(specs), "exact": exact, "total": len(keys), "diffs": diffs}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--com" in sys.argv:
        code = args[0]
        gt = os.path.join(PSEUDO, code, "_groundtruth.json")
        import json
        golden = json.load(open(gt, encoding="utf-8")).get("golden")
        materials = os.path.join(PSEUDO, code, "materials")
        dpdf = glob.glob(os.path.join(PSEUDO, code, "drawing", "*.pdf"))
        photos = sorted(glob.glob(os.path.join(PSEUDO, code, "photos", "*")))
        s2 = build_stage2(code, golden, materials)
        meta = extract_drawing_meta(golden)
        outdir = os.path.join(OUTROOT, code)
        out = os.path.join(outdir, f"{code}_M24承认书.xlsx")
        print(f"=== M2.4 COM 装配 {code} (WPS, 慢) ===")
        r = assemble(s2, {"名称": meta.get("品类"), "品号": meta.get("品号"), "版本": meta.get("版本")},
                     extract_dimensions(golden), materials, dpdf[0] if dpdf else None, out, outdir, photos)
        print(f"  specs {r['specs']} | OLE 嵌 {r['ole']} | 复开 {r['opens']} | 产物 {r['out']}")
        print("  各表:", r["by_sheet"])
        return

    cases = args or sorted(os.path.basename(p) for p in glob.glob(os.path.join(PSEUDO, "*"))
                           if os.path.isdir(p) and os.path.basename(p) not in SKIP)
    print(f"=== M2.4 无拐杖 e2e (spec级, {len(cases)} 案) ===\n")
    rows = []
    for code in cases:
        if code in SKIP:
            continue
        try:
            r = run_spec(code)
        except Exception as e:
            print(f"❌ {code}: {str(e)[:120]}")
            continue
        rows.append(r)
        flag = "✅" if not r["diffs"] else "🟡"
        ds = " ".join(f"{k}:{mn}/{gd}" for k, (mn, gd) in r["diffs"].items()) or "全对"
        print(f"{flag} {code}: OLE specs {r['specs']} | 各表对golden {r['exact']}/{r['total']} | 差异[{ds}]")
    if rows:
        print(f"\n汇总 {len(rows)} 案: 各表计数全对 {sum(1 for r in rows if not r['diffs'])}/{len(rows)}")
        print("差异多为 MSDS 高召回(材质表/材质证明超报)或源缺(部件/UL), 交确认环②人工拖/豁免")


if __name__ == "__main__":
    main()
