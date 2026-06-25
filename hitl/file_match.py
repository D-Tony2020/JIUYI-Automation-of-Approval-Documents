# -*- coding: utf-8 -*-
"""片内匹配:材料文件名 → BOM 行(料/零件)。无 golden 时取代 spatial_order 的空间对应。

C 路由器定"文件→哪张表"; 本模块定"表内→哪个料/零件槽"。靠文件名 token 模糊匹配。
匹配不准的由确认环② 拖拽纠正(=A2 边键边联想匹配的反向)。
"""
import re

COLORS = ["黑", "白", "红", "蓝", "黄", "紫", "橙", "灰", "绿", "米", "棕", "透明"]
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
    """BOM 材质名 → 候选匹配 token(含别名 + 自身字符串)。"""
    toks = {matname}
    for canon, al in ALIAS.items():
        if canon in matname or any(a in matname for a in al):
            toks.update(al); toks.add(canon)
    return {_norm(t) for t in toks if t}


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
        # 颜色物料(油墨等)分色: 名带色且文件名同色 → 加成; 异色 → 重罚
        mcol = _color(name)
        if mcol:
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
