# -*- coding: utf-8 -*-
"""OLE 放置质量闭环 — 补上"只查计数/能开、漏查落点"的洞。

对每案, COM 读 我的承认书 vs golden 每张 OLE 表的几何, 检:
  ① 自重叠   同表内两 OLE 框相交(=布局错, 如之前材质证明书浮空压图标)
  ② 计数     mine vs golden
  ③ 对齐距离 mine 每个 OLE 到 golden 最近 OLE 的中心距均值(大=错位)
  ④ 浮空     落在默认兜底锚(T≈250)或远离表区的
并逐表导出 PNG 到 产出留档/_ole审查/<案>/ 供视觉复核(放置质量必须眼睛能看)。
"""
import sys, io, os, glob, re, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from hitl.ole_assemble import com_session
import fitz

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MINE_DIR = os.path.join(ROOT, "产出留档", "M2.1-走骨架")
CASES_DIR = os.path.join(ROOT, "案例材料", "承认书", "参考用承诺书集")
REVIEW = os.path.join(ROOT, "产出留档", "_ole审查")
OLE_SHEET_KW = ("材质成分", "材质证明", "部件", "UL", "信赖", "包装", "出货", "图纸")


def _boxes(sh):
    n = sh.OLEObjects().Count
    out = []
    for i in range(1, n + 1):
        o = sh.OLEObjects().Item(i)
        try:
            out.append((o.Left, o.Top, o.Width, o.Height))
        except Exception:
            pass
    return out


def _overlap(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    # 缩 4pt 容差,只算明显相交
    return not (ax + aw - 4 <= bx or bx + bw - 4 <= ax or ay + ah - 4 <= by or by + bh - 4 <= ay)


def _count_overlaps(bxs):
    return sum(1 for i in range(len(bxs)) for j in range(i + 1, len(bxs)) if _overlap(bxs[i], bxs[j]))


def _center(b):
    return (b[0] + b[2] / 2, b[1] + b[3] / 2)


def _align(mine, gold):
    if not mine or not gold:
        return None
    tot = 0
    for m in mine:
        cm = _center(m)
        tot += min(math.hypot(cm[0] - _center(g)[0], cm[1] - _center(g)[1]) for g in gold)
    return round(tot / len(mine), 1)


def _floating(bxs):
    # 默认兜底锚 T≈250 或 L<60(出表区左)
    return sum(1 for (L, T, W, H) in bxs if 240 <= T <= 260 or L < 60)


def run_case(code, mine_path, golden, xl, render=True):
    wbm = xl.Workbooks.Open(os.path.abspath(mine_path), ReadOnly=True)
    wbg = xl.Workbooks.Open(os.path.abspath(golden), ReadOnly=True)
    gmap = {}
    for sh in wbg.Worksheets:
        if any(k in sh.Name for k in OLE_SHEET_KW):
            gmap[sh.Name.strip()] = _boxes(sh)
    rows = []
    if render:
        os.makedirs(os.path.join(REVIEW, code), exist_ok=True)
    for sh in wbm.Worksheets:
        if not any(k in sh.Name for k in OLE_SHEET_KW):
            continue
        mb = _boxes(sh)
        gb = gmap.get(sh.Name.strip(), [])
        if not mb and not gb:
            continue
        rows.append({"sheet": sh.Name.strip()[:12], "m": len(mb), "g": len(gb),
                     "overlap": _count_overlaps(mb), "align": _align(mb, gb), "float": _floating(mb)})
        if render and mb:
            p = os.path.join(REVIEW, code, f"{sh.Name.strip()[:10]}.pdf")
            try:
                sh.Select(); sh.ExportAsFixedFormat(0, os.path.abspath(p), IgnorePrintAreas=True)
                d = fitz.open(p); d[0].get_pixmap(dpi=120).save(p[:-4] + ".png"); d.close()
                os.remove(p)
            except Exception:
                pass
    wbm.Close(False); wbg.Close(False)
    return rows


def main():
    cases = sorted([p for p in glob.glob(os.path.join(CASES_DIR, "*.xlsx"))
                    if not os.path.basename(p).startswith("~$")])
    print("=== OLE 放置质量闭环 (mine vs golden) ===\n")
    print(f"{'案/表':<22}{'mine/gold':>10}{'重叠':>5}{'对齐px':>8}{'浮空':>5}  判")
    with com_session() as xl:
        for g in cases:
            code = re.sub(r"[^A-Za-z0-9]", "", os.path.basename(g))[:10]
            mine = os.path.join(MINE_DIR, code, f"{code}_无拐杖承认书.xlsx")
            if not os.path.exists(mine):
                continue
            try:
                rows = run_case(code, mine, g, xl)
            except Exception as e:
                print(f"{code}: ❌ {str(e)[:70]}"); continue
            print(f"{code}")
            for r in rows:
                bad = []
                if r["overlap"] > 0: bad.append("重叠")
                if r["float"] > 0: bad.append("浮空")
                if r["m"] != r["g"]: bad.append("计数")
                if r["align"] is not None and r["align"] > 120: bad.append("错位")
                flag = "✅" if not bad else "❌" + "/".join(bad)
                al = f"{r['align']}" if r["align"] is not None else "-"
                print(f"  {r['sheet']:<20}{r['m']:>4}/{r['g']:<5}{r['overlap']:>5}{al:>8}{r['float']:>5}  {flag}")
    print(f"\n渲染留档: {REVIEW}/<案>/<表>.png  (逐表视觉复核)")
    print("判据: 重叠>0=布局错; 浮空>0=兜底位; 计数≠golden; 对齐>120px=放错行/列")


if __name__ == "__main__":
    main()
