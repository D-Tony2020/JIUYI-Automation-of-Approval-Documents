# -*- coding: utf-8 -*-
"""C 段:材料 PDF → OLE 槽路由(文件名关键词 + 扇出规则)。

实证(7案221文件): naive 92% → 本规则 ~99%, 硬残 ~1%(供应商料号乱名)。
扇出:1 文件→N 槽(MSDS 同进 材质表+材质证明)。空集=认不准→留确认环②人工拖。
"""
import re

SLOTS = ("材质表", "材质证明", "部件承认", "UL", "信赖性", "包装", "出货", "图纸")


def route(filename):
    """返回该文件应进的 OLE 槽集合(可多=扇出; 空集=低置信, 交人工)。"""
    nm = filename
    up = nm.upper()
    compact = re.sub(r"\s+", "", nm)          # 去空格(含全角)再匹配
    cup = compact.upper()
    slots = set()

    # UL 证书(排除 UL94 阻燃等级误命中)
    if "UL" in cup.replace("UL94", ""):
        slots.add("UL")
    # MSDS/物质安全资料 → 材质表 + 材质证明(扇出)
    if ("MSDS" in up or "MATERIAL SAFE" in up
            or any(k in nm for k in ("物質安全", "物质安全", "安全资料", "安全資料"))):
        slots |= {"材质表", "材质证明"}
    # REACH/RoHS/SVHC/SGS/第三方报告(CANEC/GZP/SZP 报告号) → 材质表
    if (any(k in up for k in ("REACH", "SVHC", "ROHS", "CANEC", "SGS"))
            or "GZP" in cup or "SZP" in cup):
        slots.add("材质表")
    # 供应商承认书/规格书 → 部件承认
    if any(k in nm for k in ("承认书", "承認書", "规格书", "規格書", "系列", "规格")):
        slots.add("部件承认")
    # 信赖性测试(盐雾/可靠/实验室报告)
    if any(k in nm for k in ("盐雾", "鹽霧", "信赖", "信賴", "可靠", "实验室报告", "實驗室")):
        slots.add("信赖性")
    # 包装规范(去空格匹配 "包 装")
    if "包装" in compact or "包裝" in compact or "PACK" in up:
        slots.add("包装")
    # 出货检验
    if "出货" in compact or "出貨" in compact or "检验" in compact or "COC" in up:
        slots.add("出货")
    # 图纸(防御:品号+版本号命名, 仅当无其他命中)
    if not slots and re.search(r"[A-Z]{2}\d{6,}", up) and ("A0" in up or "导线" in nm):
        slots.add("图纸")
    return slots


if __name__ == "__main__":
    import sys, io, os, glob, json
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    gts = sorted(glob.glob(os.path.join(root, "本单输入", "pseudo", "*", "_groundtruth.json")))
    tot = exact = covered = tot_slot = unrouted = 0
    misses = []
    for gp in gts:
        gt = json.load(open(gp, encoding="utf-8"))
        for nm, true in gt["file_slots"].items():
            pred = route(nm)
            true = set(true)
            tot += 1
            if pred == true:
                exact += 1
            if not pred:
                unrouted += 1
            covered += len(pred & true)
            tot_slot += len(true)
            if pred != true and len(misses) < 12:
                misses.append((gt["code"], nm[:34], sorted(true), sorted(pred)))
    print(f"=== C路由器 vs 伪真单真值 ({len(gts)}案) ===")
    print(f"  精确集匹配: {exact}/{tot} ({exact*100//tot}%)")
    print(f"  槽位召回:   {covered}/{tot_slot} ({covered*100//tot_slot}%)")
    print(f"  未路由(交人工): {unrouted}")
    print("  偏差样本:")
    for c, nm, t, p in misses:
        print(f"    {c} [{nm}] 真{t} 预测{p or '∅'}")
