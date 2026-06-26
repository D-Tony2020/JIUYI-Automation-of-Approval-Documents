# -*- coding: utf-8 -*-
"""文件↔材质链(M2.3→M2.4 交接物): 每个 B提议材质配齐它的报告文件 → M2.4 OLE 据此落 K/L/Y 格。

分工: C路由器 file_router.route 定"文件进哪张表"; 本模块在'材质表/材质证明'内
(1) 细分报告类型(MSDS/RoHS/REACH/SVHC) (2) 用 file_match 把文件对到具体材质。
认不准的进 unlinked, 交确认环②(文件树)人工拖。MSDS=材质的源文件已知, 不重复链。
"""
import glob
import os
import re

from hitl.file_match import ALIAS, _color, _norm
from hitl.file_router import route


def report_type(filename):
    """材质表/材质证明内的报告细分类型。MSDS 与第三方报告(RoHS/REACH/SVHC)分开放不同格。"""
    up = filename.upper()
    compact = re.sub(r"\s+", "", up)
    if ("MSDS" in up or "MATERIAL SAFE" in up
            or any(k in filename for k in ("物質安全", "物质安全", "安全资料", "安全資料"))):
        return "MSDS"
    if "REACH" in up:
        return "REACH"
    if "SVHC" in up:
        return "SVHC"
    if "ROHS" in up or "CANEC" in compact or "GZP" in compact or "SZP" in compact:
        return "RoHS"
    return "其他"


def _ident(material):
    """材质身份: (别名规范token集, 颜色)。token 取自 材质名 + MSDS源文件名(同料的MSDS与报告共享识别词:
    锡线/镀锡/PA66/端子/热缩——报告名常用通用词, 与商品名(FRIANYL/Sn-0.7Cu)对不上, 但与MSDS文件名对得上)。"""
    name = str(material.get("材质", ""))
    hay = _norm(name) + _norm(material.get("源文件", ""))
    toks = set()
    for canon, al in ALIAS.items():
        variants = [canon] + list(al)
        if any(_norm(v) in hay for v in variants):
            toks.update(_norm(v) for v in variants)
    for pw in ("端子", "胶粒", "塑胶"):               # 部件型通用词: 材质名含则加(报告名爱用"端子ROHS"等通用词)
        if pw in name:
            toks.add(_norm(pw))
    if "油墨" in name:                                # 油墨同类多色: 颜色消歧
        toks.add("油墨")
    return toks, _color(name)


def _usable_tok(t):
    """可用于报告匹配的 token: 含中文 或 字母数字≥4位。丢单字元素(铜/锡)+短合金码(C26/C5)——
    后者会撞报告号数字(端子号 SHAEC26005 含 'C26' → 误吸到镀锡铜)。保 C5191/PA66/镀锡/端子。"""
    return len(t) >= 4 or any("一" <= c <= "鿿" for c in t)


def _match_report(filename, mats_ident):
    """报告文件 → 身份token重叠最长的材质 index。颜色仅在已命中料名时消歧。无把握 None。"""
    fn = _norm(filename)
    fcol = _color(filename)
    best, bs = None, 0
    for i, (toks, mcol) in enumerate(mats_ident):
        s = max((len(t) for t in toks if _usable_tok(t) and t in fn), default=0)
        if s and mcol:                               # 已命中料名→颜色消歧(白/黑油墨)
            s = s + 6 if fcol == mcol else (s - 10 if fcol and fcol != mcol else s)
        if s > bs:
            best, bs = i, s
    return best if bs > 0 else None


def link_materials(materials_dir, proposals):
    """→ (linked, unlinked)。
    linked = proposals 副本, 每项加 files={MSDS:源文件, RoHS:[], REACH:[], SVHC:[], 其他:[]}。
    unlinked = [(base, 类型)] 认不准的报告文件, 交确认环②人工拖。
    """
    mats_ident = [_ident(p) for p in proposals]
    linked = [dict(p, files={"MSDS": p.get("源文件"), "RoHS": [], "REACH": [], "SVHC": [], "其他": []})
              for p in proposals]
    unlinked = []
    src_set = {p.get("源文件") for p in proposals}
    for f in sorted(glob.glob(os.path.join(materials_dir, "*.pdf"))):
        base = os.path.basename(f)
        slots = route(base)
        if "材质表" not in slots and "材质证明" not in slots:
            continue
        rt = report_type(base)
        if rt == "MSDS" or base in src_set:        # MSDS 已是材质源文件, 不重复链
            continue
        mi = _match_report(base, mats_ident)
        if mi is None:
            unlinked.append((base, rt))
            continue
        linked[mi]["files"][rt].append(base)
    return linked, unlinked


_TYPE_COL = {"RoHS": "Y", "REACH": "L", "SVHC": "L", "其他": "K", "MSDS": "K"}


def suggest_for(filename, typ, materials):
    """认不准报告 → 建议归属(比 link 低阈值: 弱token主、颜色兜底纯色号报告)。

    用 BOM 操作员确认的 材质名/零件 增量归属(老板要的连续性)。颜色只能区别不能唯一定材→只建议不自动挂。
    返回 {材质, 零件, col, 据} 或 None。
    """
    fn = _norm(filename)
    fcol = _color(filename)
    col = _TYPE_COL.get(typ, "L")
    best, bs = None, 0
    for i, m in enumerate(materials):                # ① 名/源文件 distinctive token(主)
        if m.get("豁免"):
            continue
        toks, _mc = _ident(m)
        s = max((len(t) for t in toks if _usable_tok(t) and t in fn), default=0)
        if s > bs:
            bs, best = s, (i, m)
    if best:
        i, m = best
        return {"idx": i, "材质": m.get("材质", ""), "零件": m.get("零件", ""), "col": col, "据": "名"}
    if fcol:                                          # ② 无token → 颜色兜底(纯色号CANEC墨报告)
        for i, m in enumerate(materials):
            if not m.get("豁免") and _color(m.get("材质", "")) == fcol:
                return {"idx": i, "材质": m.get("材质", ""), "零件": m.get("零件", ""), "col": col, "据": "色"}
    return None


def suggest_unlinked(materials, unlinked):
    """给每个认不准报告附建议归属(操作员一点即挂)。unlinked=[{文件,类型}]。"""
    out = []
    for u in unlinked or []:
        out.append(dict(u, 建议=suggest_for(u.get("文件", ""), u.get("类型", ""), materials)))
    return out


if __name__ == "__main__":
    import io
    import json
    import sys

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from hitl.material_extract import propose_bom_from_pile
    from study.golden_parse import parse_golden

    code = sys.argv[1] if len(sys.argv) > 1 else "YY60039403"
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    gt = json.load(open(os.path.join(root, "本单输入", "pseudo", code, "_groundtruth.json"), encoding="utf-8"))
    md = os.path.join(root, "本单输入", "pseudo", code, "materials")

    props = propose_bom_from_pile(md)
    linked, unlinked = link_materials(md, props)
    print(f"=== 文件↔材质链 {code} (B提议{len(props)}材质) ===")
    for p in linked:
        fz = p["files"]
        rep = " ".join(f"{k}×{len(fz[k])}" for k in ("RoHS", "REACH", "SVHC", "其他") if fz[k])
        print(f"  [{p['材质']}]  MSDS={fz['MSDS']}  报告: {rep or '∅'}")
    if unlinked:
        print(f"  认不准(交人工)×{len(unlinked)}: " + " / ".join(f"{b[:30]}({t})" for b, t in unlinked))

    # 对标 golden 报告号: golden 每材质报告块的 报告号 应出现在某文件名中, 且该文件链到对的材质
    print(f"\n=== 对标 golden 报告号(文件↔材质链正确性) ===")
    gmats = parse_golden(gt["golden"])

    def _norm(s):
        return re.sub(r"\s+", "", str(s or "")).upper()
    allfiles = [os.path.basename(x) for x in glob.glob(os.path.join(md, "*.pdf"))]
    hit = miss_file = 0
    for gm in gmats:
        for blk in gm.get("blocks", []):
            no = _norm(blk.get("报告号"))
            if len(no) < 6:
                continue
            owner = next((b for b in allfiles if no in _norm(b)), None)
            if not owner:
                miss_file += 1
                continue
            hit += 1
    print(f"  golden 报告号在料堆能定位到文件: {hit} (缺文件 {miss_file})")
