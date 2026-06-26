# -*- coding: utf-8 -*-
"""M2.3 无拐杖伪真单 e2e: files-first·B提议(真 qwen, 从原始料堆) → 对标 golden BOM。

不碰 golden 拐杖。propose_bom_from_pile 自己 C 分类 + 选真 MSDS + B 抽成分提议材质;
本测量它对 golden 材质的:
  (1) 覆盖率  = 有 B 提议命中的 golden 材质 / golden 材质总数
  (2) CAS块级召回 = 每个命中材质 B 抽到的 CAS ∩ golden CAS / golden CAS
  (3) 漏提议(golden 有 B 无, 多因无 MSDS 只 REACH) / 多提议(B 有 golden 无, 多因重复上传)
按 CAS 集合重叠对齐 B↔golden(绕开材质命名差异), 贪心取最大重叠。

用法: python run_m23_e2e.py [案号...]   (不给则跑全部 pseudo 案; 注意非缓存案会真烧 qwen)
"""
import glob
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from study.golden_parse import parse_golden
from hitl.material_extract import propose_bom_from_pile

PSEUDO = os.path.join(ROOT, "本单输入", "pseudo")


def _cas_set(comps, key):
    out = set()
    for c in comps or []:
        v = str(c.get(key) or "").strip().replace(" ", "")
        if not v or v in ("/", "-"):
            continue
        for part in v.replace("、", ",").replace(";", ",").split(","):
            p = part.strip()
            if p and p not in ("/", "-"):
                out.add(p)
    return out


def _gt_golden(code):
    import json
    gt = os.path.join(PSEUDO, code, "_groundtruth.json")
    return json.load(open(gt, encoding="utf-8")).get("golden")


def match(b_mats, g_mats):
    """单射对齐 B↔golden(每 B 只用一次, 防子集假命中如 纯锡→镀锡铜)。
    候选(jaccard,recall,gi,bi) 按 jaccard 降序贪心分配。→ {g_idx:(b_idx,recall)}, extra_b[]。"""
    g_cas = [_cas_set(g.get("components"), "CAS") for g in g_mats]
    b_cas = [_cas_set(b.get("成份"), "CAS") for b in b_mats]
    cand = []
    for gi, gc in enumerate(g_cas):
        if not gc:
            continue
        for bi, bc in enumerate(b_cas):
            inter = len(bc & gc)
            if not inter:
                continue
            jac = inter / len(bc | gc)
            cand.append((jac, inter / len(gc), gi, bi))
    cand.sort(reverse=True)
    g_match, used_b = {}, set()
    for jac, recall, gi, bi in cand:
        if gi in g_match or bi in used_b:
            continue
        g_match[gi] = (bi, recall, "cas")
        used_b.add(bi)
    # 名/源文件兜底: CAS没对上的(聚合物多CAS号: PA66源37640-57-6 vs golden63428-84-2)按材质名substring对(操作员就这么认)
    def _norm(s):
        return "".join(str(s or "").split()).upper()
    for gi in range(len(g_mats)):
        if gi in g_match:
            continue
        gname = _norm(g_mats[gi].get("材质"))
        if len(gname) < 4:                       # 太短(锡/铜)易误配, 只信CAS
            continue
        for bi in range(len(b_mats)):
            if bi in used_b:
                continue
            if gname in _norm(b_mats[bi].get("材质")) + _norm(b_mats[bi].get("源文件")):
                g_match[gi] = (bi, None, "name")  # 名兜底(非CAS对): 不计入CAS召回
                used_b.add(bi)
                break
    extra_b = [bi for bi in range(len(b_mats)) if bi not in used_b]
    return g_match, extra_b


def run_case(code):
    golden = _gt_golden(code)
    materials = os.path.join(PSEUDO, code, "materials")
    if not golden or not os.path.isdir(materials):
        return {"code": code, "err": "缺 golden 或 materials"}
    g_mats = parse_golden(golden)
    b_mats = propose_bom_from_pile(materials)
    g_match, extra_b = match(b_mats, g_mats)
    recalls = [sc for (_, sc, how) in g_match.values() if how == "cas"]
    name_cnt = sum(1 for (_, _, how) in g_match.values() if how == "name")
    missing = [str(g_mats[gi].get("材质") or "?") for gi in range(len(g_mats)) if gi not in g_match]
    extra = [str(b_mats[bi].get("材质") or "?") for bi in extra_b]
    return {
        "code": code, "golden材质": len(g_mats), "B提议": len(b_mats),
        "覆盖": len(g_match), "覆盖率": len(g_match) / len(g_mats) if g_mats else 0,
        "CAS对": len(recalls), "名兜底对": name_cnt,
        "CAS召回均": sum(recalls) / len(recalls) if recalls else 0.0,
        "漏": missing, "多提议": extra,
    }


def dryrun(cases):
    """预检(零 qwen): 每案 golden材质数 + 过文本门的候选MSDS + 缓存/需实时, 估这一把要烧几次。"""
    from hitl.material_extract import candidate_msds, is_extract_cached
    print(f"=== 预检(零 qwen 调用, {len(cases)} 案) ===\n")
    total_live = 0
    for code in cases:
        golden = _gt_golden(code)
        materials = os.path.join(PSEUDO, code, "materials")
        if not golden or not os.path.isdir(materials):
            print(f"⏭  {code}: 缺 golden 或 materials")
            continue
        g = len(parse_golden(golden))
        cands = candidate_msds(materials)
        cached = sum(1 for (_b, txt, _f) in cands if is_extract_cached(txt))
        live = len(cands) - cached
        total_live += live
        print(f"{code}: golden材质{g} | 候选MSDS{len(cands)}(缓存{cached} 需实时{live})")
        for b, txt, _f in cands:
            print(f"      {'✓缓存' if is_extract_cached(txt) else '●实时'} {b}")
    print(f"\n充值后跑全量需实时 qwen 调用 ≈ {total_live} 次(其余命中缓存)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    cases = args or sorted(os.path.basename(p) for p in glob.glob(os.path.join(PSEUDO, "*"))
                           if os.path.isdir(p))
    if "--dryrun" in sys.argv:
        dryrun(cases)
        return
    print(f"=== M2.3 无拐杖伪真单 e2e ({len(cases)} 案) ===\n")
    rows = []
    for code in cases:
        try:
            r = run_case(code)
        except Exception as e:
            print(f"❌ {code}: {str(e)[:140]}")
            continue
        if r.get("err"):
            print(f"⏭  {code}: {r['err']}")
            continue
        rows.append(r)
        flag = "✅" if r["覆盖率"] >= 0.99 else ("🟡" if r["覆盖率"] >= 0.75 else "🔴")
        print(f"{flag} {r['code']}: golden材质{r['golden材质']} B提议{r['B提议']} | "
              f"覆盖{r['覆盖']}/{r['golden材质']}({r['覆盖率']*100:.0f}%) "
              f"[CAS对{r['CAS对']}+名兜底{r['名兜底对']}] CAS召回{r['CAS召回均']*100:.0f}%")
        if r["漏"]:
            print(f"      漏提议(多因无MSDS): {' / '.join(r['漏'])}")
        if r["多提议"]:
            print(f"      多提议(多因重复上传): {' / '.join(r['多提议'])}")
    if rows:
        n = len(rows)
        print(f"\n=== 汇总 {n} 案 ===")
        print(f"覆盖率均 {sum(r['覆盖率'] for r in rows)/n*100:.0f}% | "
              f"CAS块级召回均 {sum(r['CAS召回均'] for r in rows)/n*100:.0f}%")


if __name__ == "__main__":
    main()
