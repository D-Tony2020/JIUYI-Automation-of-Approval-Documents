# -*- coding: utf-8 -*-
"""片内匹配:材料文件名 → BOM 行(料/零件)。无 golden 时取代 spatial_order 的空间对应。

C 路由器定"文件→哪张表"; 本模块定"表内→哪个料/零件槽"。靠文件名 token 模糊匹配。
匹配不准的由确认环② 拖拽纠正(=A2 边键边联想匹配的反向)。
"""
import re

COLORS = ["黑", "白", "红", "蓝", "黄", "紫", "橙", "灰", "绿", "米", "棕", "透明"]
CATEGORIES = ("油墨",)   # 同类多色物料: 加类别token, 由颜色消歧(锡/铜等元素过泛, 不入此列)
# 物料同义/变体(文件名用词 ↔ BOM 材质名常不一致)
ALIAS = {
    "PVC": ["PVC", "胶料"], "PA66": ["PA66", "尼龙", "NYLON"], "PA": ["PA"],
    "镀锡铜": ["镀锡铜", "镀锡", "锡铜线"], "磷青铜": ["磷青铜", "磷铜", "磷铜端子", "C5191", "C5210"],
    "聚烯烃": ["聚烯烃", "热缩", "套管", "热缩管", "热缩套管"], "油墨": ["油墨"],
    "锡": ["无铅锡", "锡线", "焊锡", "07CU"], "铜": ["铜", "黄铜", "C26", "C5"],
}


def _norm(s):
    return re.sub(r"\s+", "", s).upper()


def _mat_tokens(matname):
    """BOM 材质名 → 候选匹配 token(含别名 + 自身字符串)。

    别名只在 材质名==canon 或 ∈别名组 时继承, 避免子串泄漏
    (锡 ⊂ 镀锡铜 → 镀锡铜 误吃 锡 的别名 07CU/锡线)。
    """
    toks = {matname}
    for canon, al in ALIAS.items():
        if matname == canon or matname in al:
            toks.update(al); toks.add(canon)
    for cat in CATEGORIES:              # 名含类别(黑色油墨⊃油墨)→加类别token; 不继承别名(避泄漏)
        if cat in matname:
            toks.add(cat)
    return {_norm(t) for t in toks if t}


def content_match(pdf_path, materials, pages=3):
    """⭐内容驱动:PDF 内容 → BOM 材质 index(比文件名可靠,内容含料名)。失败/无把握 None。

    B 段为抽成分本就要读 PDF;读内容时即知"是哪个料",此链路白来。
    """
    import fitz
    try:
        d = fitz.open(pdf_path)
        txt = "".join(d[i].get_text() for i in range(min(pages, d.page_count)))
        d.close()
    except Exception:
        return None
    t = _norm(txt)
    best, bs = None, 0
    for i, m in enumerate(materials):
        name = (m.get("材质") or "").strip()
        if not name:
            continue
        s = max((len(tok) for tok in _mat_tokens(name) if tok and tok in t), default=0)
        if s > bs:
            best, bs = i, s
    return best if bs > 0 else None


def _color(s):
    for c in COLORS:
        if c in s:
            return c
    return None


def match_material(filename, materials):
    """文件名 → 最佳匹配 BOM 材质 index。materials=[{材质,...}]。无把握返回 None。

    打分:别名 token 命中长度 + 颜色一致加成(油墨/PVC 分色)。
    """
    fn = _norm(filename)
    fcol = _color(filename)
    best, best_s = None, 0
    for i, m in enumerate(materials):
        name = (m.get("材质") or "").strip()
        if not name:
            continue
        s = 0
        for tok in _mat_tokens(name):
            if tok and tok in fn:
                s = max(s, len(tok) * 2)        # 命中越长越可信
        # 颜色仅在**已命中料名**时消歧(黑/白油墨), 不单独得分 → 避"热缩管黑色"误判黑色油墨
        mcol = _color(name)
        if mcol and s > 0:
            if fcol == mcol:
                s += 6
            elif fcol and fcol != mcol:
                s -= 10
        if s > best_s:
            best, best_s = i, s
    return best if best_s > 0 else None


if __name__ == "__main__":
    import sys, io, os, json, glob
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from hitl.file_router import route

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    bom = json.load(open(os.path.join(root, "hitl", "data", "demo_bom_YY60039403.json"), encoding="utf-8"))
    mats = [{"材质": m["材质"], "零件": p["零件"]} for p in bom for m in p["materials"]]
    print("BOM 材质行:", [f"{m['零件']}/{m['材质']}" for m in mats], "\n")

    od = os.path.join(root, "本单输入", "pseudo", "YY60039403", "materials")
    files = sorted(os.listdir(od))
    matched = unmatched = 0
    print("=== 材质表文件 → 匹配料行(锚点403, 人工核对准不准) ===")
    for f in files:
        if "材质表" not in route(f):
            continue
        mi = match_material(f, mats)
        tag = f"{mats[mi]['零件']}/{mats[mi]['材质']}" if mi is not None else "∅未匹配"
        if mi is not None:
            matched += 1
        else:
            unmatched += 1
        print(f"  {f[:46]:<46} → {tag}")
    print(f"\n匹配 {matched} / 未匹配 {unmatched}")
