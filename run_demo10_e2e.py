# -*- coding: utf-8 -*-
"""10 伪真单闭环测试: 自主管线(B提议→字典resolve→链→enrich→段一材质表) → 对标 golden 精准单元格。

parse_golden 既解析 golden 也解析我们的段一输出(同为承认书材质表)→ 直接逐格对比。
产出: (1) 每单精准单元格匹配率(材质/成份名/CAS/重量%/RoHS) (2) 我们的cell xlsx存盘供眼测。
用法: python run_demo10_e2e.py            # 跑全部10单
      python run_demo10_e2e.py YY60010118 # 跑单个
"""
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import datetime

import openpyxl

from hitl.assemble_order import BLANK
from hitl.dicts import alias_table, catpart_table, resolve_material
from hitl.drawing_extract import extract as draw_extract
from hitl.file_link import link_materials
from hitl.material_extract import enrich_rohs, propose_bom_from_pile
from hitl.material_table import fill_material_table
from hitl.placement_plan import stage2_to_nested_bom
from study.golden_parse import parse_golden

OUT = os.path.join(ROOT, ".work", "demo10")
CASES = os.path.join(ROOT, "案例材料", "承认书", "参考用承诺书集")


def _golden_path(code):
    for g in glob.glob(os.path.join(CASES, "*.xlsx")):
        if code in os.path.basename(g) and not os.path.basename(g).startswith("~$"):
            return g
    return None


def autonomous(code):
    """自主管线(无操作员): B提议→字典resolve→file链→enrich RoHS → stage2_bom。"""
    md = os.path.join(ROOT, "本单输入", "pseudo", code, "materials")
    props = propose_bom_from_pile(md)
    alias, catpart = alias_table(), catpart_table()
    for m in props:
        r = resolve_material(m.get("材质原文") or m.get("材质", ""), alias, catpart)
        m["材质"] = r["标准名"] or m.get("材质", "")
        m["材质类别"] = r["材质类别"]
        m["零件"] = r["零件"]
    linked, unlinked = link_materials(md, props)
    enrich_rohs(linked, md)
    return {"materials": linked, "unlinked_files": [{"文件": f, "类型": t} for f, t in unlinked]}


def our_xlsx(code, stage2):
    """只填材质表(无COM, 不走cover校验) → cell xlsx 路径。本测专注材质表逐格对标。"""
    draw = glob.glob(os.path.join(ROOT, "本单输入", "pseudo", code, "drawing", "*.pdf"))
    meta = {"名称": "", "品号": "", "版本": ""}
    if draw:
        try:
            d = draw_extract(draw[0])
            meta = {"名称": d["名称"], "品号": d["品号"], "版本": d["版本"]}
        except Exception:
            pass
    od = os.path.join(OUT, code)
    os.makedirs(od, exist_ok=True)
    wb = openpyxl.load_workbook(BLANK)
    ws = next(wb[s] for s in wb.sheetnames if "材质成分" in s)
    nested, _ = stage2_to_nested_bom(stage2["materials"])
    name = (meta.get("名称") or "导线").strip() or "导线"
    fill_material_table(ws, nested, {"材料名称": name, "填表日期": datetime.date(2026, 6, 27)})
    cell = os.path.join(od, code + "_matsheet.xlsx")
    wb.save(cell)
    return cell, meta


# ── 精准单元格对比 ────────────────────────────────────────────
def _cas(comps):
    return {(c.get("CAS") or "").replace(" ", "") for c in comps if (c.get("CAS") or "").strip() not in ("", "/", "-")}


def _match(ours, gold):
    """单射对齐 我们↔golden(CAS集合最大重叠, 名兜底), 每golden只配一次。"""
    pairs, used = [], set()
    for gi, g in enumerate(gold):
        gc = _cas(g["components"])
        best, bi = -1, None
        for oi, o in enumerate(ours):
            if oi in used:
                continue
            oc = _cas(o["components"])
            ov = len(gc & oc)
            if ov == 0 and g["材质"] and o["材质"]:                 # 名兜底(聚合物多CAS号对不上)
                if g["材质"] in o["材质"] or o["材质"] in g["材质"]:
                    ov = 0.5
            if ov > best:
                best, bi = ov, oi
        if bi is not None and best > 0:
            used.add(bi); pairs.append((ours[bi], g))
    return pairs


def _num(v):
    s = str(v or "").strip().replace("%", "")
    try:
        return float(s)
    except Exception:
        return None


def _wmatch(ov, gv):
    """重量%匹配(范围感知): golden 单元格混合格式——小数(0.99)/百分数范围(10-30%)/余量/<x。
    我们存小数占比。范围→我们值(×100)落区间; 单值→±25%; 余量/<x→字符串。
    返回 True/False, 或 None(golden空, 不计)。
    """
    import re
    g, o = str(gv or "").strip(), str(ov or "").strip()
    if not g:
        return None
    if g.replace(" ", "") == o.replace(" ", ""):
        return True
    if "余量" in g or g[:1] in "<>≤≥＜＞〈〉":
        return g.replace(" ", "") == o.replace(" ", "")
    on = _num(ov)
    nums = [float(x) for x in re.findall(r"\d*\.?\d+(?:[eE][-+]?\d+)?", g)]   # 科学计数法4e-05算一个数(非范围)
    if on is None or not nums:
        return g == o
    pct = ("%" in g) or (len(nums) >= 2) or (max(nums) > 1)   # golden 是百分数刻度
    op = on * 100 if pct else on
    if len(nums) >= 2:                                        # 范围: 我们值落[min,max](±20%放宽)
        return min(nums) * 0.8 <= op <= max(nums) * 1.2
    return abs(op - nums[0]) <= max(nums[0], 1e-6) * 0.25


def compare(ours, gold):
    """逐格对比 → 计数 {项: [对, 总]}。"""
    R = {k: [0, 0] for k in ("材质覆盖", "材质名", "材质类别", "零件", "成份名(G)", "CAS(H)",
                             "重量%单值", "重量%区间", "RoHS(M-V)")}
    R["材质覆盖"] = [0, len(gold)]
    pairs = _match(ours, gold)
    R["材质覆盖"][0] = len(pairs)
    for o, g in pairs:
        for key, of, gf in (("材质名", o.get("材质"), g.get("材质")),
                            ("材质类别", o.get("材质类别"), g.get("材质类别")),
                            ("零件", o.get("零件"), g.get("零件"))):
            R[key][1] += 1
            if of and gf and (str(of).strip() == str(gf).strip() or str(gf).strip() in str(of).strip() or str(of).strip() in str(gf).strip()):
                R[key][0] += 1
        # 成份: 按 CAS 对齐
        ocomp = {(c.get("CAS") or "").replace(" ", ""): c for c in o["components"]}
        for gc in g["components"]:
            cas = (gc.get("CAS") or "").replace(" ", "")
            R["CAS(H)"][1] += 1
            if cas and cas in ocomp:
                R["CAS(H)"][0] += 1
                oc = ocomp[cas]
                R["成份名(G)"][1] += 1
                if (oc.get("成份名") or "").strip() and (oc.get("成份名") or "").strip() == (gc.get("成份名") or "").strip():
                    R["成份名(G)"][0] += 1
                wm = _wmatch(oc.get("重量%"), gc.get("重量%"))
                if wm is not None:
                    import re as _re
                    gn = _re.findall(r"\d*\.?\d+(?:[eE][-+]?\d+)?", str(gc.get("重量%") or "").replace("%", ""))
                    key = "重量%区间" if len(gn) >= 2 else "重量%单值"   # golden 是范围(10-30)还是单值
                    R[key][1] += 1
                    if wm:
                        R[key][0] += 1
        # RoHS: 块级首 block 的 10 项
        ob = (o.get("blocks") or [{}])[0].get("rohs", {})
        gb = (g.get("blocks") or [{}])[0].get("rohs", {})
        for k in (gb or {}):
            R["RoHS(M-V)"][1] += 1
            if str(ob.get(k, "")).strip() and str(ob.get(k, "")).strip().upper() == str(gb.get(k, "")).strip().upper():
                R["RoHS(M-V)"][0] += 1
    return R, pairs


def main():
    codes = sys.argv[1:] or json.load(open(os.path.join(ROOT, ".work", "_demo10_codes.json")))
    agg = {}
    print(f"=== 10伪真单闭环 · 自主管线对标golden精准单元格 ({len(codes)}单) ===\n")
    for code in codes:
        gp = _golden_path(code)
        if not gp:
            print(f"❌ {code}: 无golden"); continue
        try:
            stage2 = autonomous(code)
            cell, meta = our_xlsx(code, stage2)
            ours = parse_golden(cell)             # 解析我们的段一材质表
            gold = parse_golden(gp)               # golden材质表
            R, pairs = compare(ours, gold)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"❌ {code}: {str(e)[:80]}"); continue
        cov = f"{R['材质覆盖'][0]}/{R['材质覆盖'][1]}"
        line = " ".join(f"{k}{v[0]}/{v[1]}" for k, v in R.items() if k != "材质覆盖" and v[1])
        print(f"✅ {code} 品号{meta['品号'][:12]:12} 覆盖{cov} | {line}")
        for k, v in R.items():
            a = agg.setdefault(k, [0, 0]); a[0] += v[0]; a[1] += v[1]
    print("\n===== 汇总(10单合计) =====")
    for k, v in agg.items():
        pct = f"{v[0] * 100 // v[1]}%" if v[1] else "—"
        print(f"  {k:12} {v[0]}/{v[1]}  {pct}")


if __name__ == "__main__":
    main()
