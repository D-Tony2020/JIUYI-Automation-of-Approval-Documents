# -*- coding: utf-8 -*-
"""嵌入组结构搭建（固化）：槽位数由 BOM 算 + N 槽位网格布局。供 W6 总装结构驱动。

- embed_group_count(materials): BOM → 各嵌入组表槽位数。
- grid_anchors(n, ...): N 个槽位的 (Left,Top) 网格坐标（单行类/网格类通用）。
验证：对各案重算计数，应等于实测 OLE 数（见 ole_structure；YY60039397 源缺除外）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# 工艺材料：是材质但无"供应商部件承认书/UL"（锡=焊料）
PROCESS_PARTS = {"锡", "锡膏", "焊锡", "助焊"}

# 各嵌入组表布局参数（实证 golden）：x0,y0 首槽; per_row 每行槽数(单行类给大数); dx,dy 步距; w,h 槽尺寸
GRID = {
    "材质证明书": dict(x0=105, y0=283, per_row=4, dx=76, dy=80, w=64, h=42),
    "部件承认书": dict(x0=112, y0=316, per_row=9, dx=110, dy=60, w=84, h=42),
    "UL证明":   dict(x0=103, y0=279, per_row=9, dx=120, dy=60, w=78, h=51),
    "信赖性":   dict(x0=113, y0=308, per_row=9, dx=140, dy=60, w=115, h=42),
}


def 采购部件(materials):
    """distinct 零件去掉工艺料(锡)。"""
    parts = []
    for m in materials:
        p = (m.get("零件") or "").strip()
        if p and p not in parts and not any(k in p for k in PROCESS_PARTS):
            parts.append(p)
    return parts


def embed_group_count(materials):
    """BOM(materials=golden_parse 输出) → 各嵌入组表应有槽位数。"""
    nmat = len(materials)
    nparts = len(采购部件(materials))
    return {
        "图纸": 1,
        "部件承认书": nparts,
        "UL证明": nparts,            # 每采购件一张 UL（实证 7/7 = 部件承认书）
        "材质证明书": nmat,           # 一材一证
        "信赖性": max(1, nparts - 1),  # 较松，~部件数
        "包装": 1,
        "出货": 1,
    }


def grid_anchors(n, x0, y0, per_row, dx, dy, **_):
    """N 个槽位的 (Left, Top) 列表：每行 per_row 个，X 步 dx、Y 步 dy。"""
    return [(x0 + (i % per_row) * dx, y0 + (i // per_row) * dy) for i in range(n)]


# 材质证明书：按零件分组（每零件其材质数张证明横排在该零件标签行）。
# 各零件行 Top 实证 golden（对应模板标签 B12线材/B14胶壳端子/B17套管/B20锡）。
MATCERT_PART_TOPS = [283, 343, 420, 505]
MATCERT_X0, MATCERT_DX = 105, 76
MATCERT_W, MATCERT_H = 64, 42


def matcert_anchors(bom):
    """材质证明书按零件分组的证明位置 [(L, T)]：每零件其材质数张横排在该零件行。

    bom=零件list(每零件含 materials)。换产品时零件数/每零件材质数变, 分组自动跟着对。
    """
    pos = []
    for i, part in enumerate(bom):
        top = (MATCERT_PART_TOPS[i] if i < len(MATCERT_PART_TOPS)
               else MATCERT_PART_TOPS[-1] + (i - len(MATCERT_PART_TOPS) + 1) * 82)
        for j in range(len(part.get("materials", []))):
            pos.append((MATCERT_X0 + j * MATCERT_DX, top))
    return pos


def spatial_order(specs):
    """按 golden 空间序排 specs（行分组：T 相近为同行，行内按 L 左→右），保文件↔标签对应。

    装配按结构算位置(grid/part)是按"顺序"填的；必须先让 specs 的顺序 = golden 里的
    左右上下顺序，最左的才落到算出位置的最左槽——否则文件与标签装反。
    """
    s = sorted(specs, key=lambda x: (x.get("T", 0), x.get("L", 0)))
    rows, cur, last = [], [], None
    for sp in s:
        t = sp.get("T", 0)
        if last is not None and t - last > 25:   # T 跳变>25pt=换行
            rows.append(cur); cur = []
        cur.append(sp); last = t
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        out.extend(sorted(r, key=lambda x: x.get("L", 0)))
    return out


def count_from_bom(bom):
    """W6 用：吃 demo_bom（零件list，每零件含 materials）→ 各嵌入组表槽位数。"""
    nmat = sum(len(p.get("materials", [])) for p in bom)
    nparts = len([p for p in bom
                  if not any(k in (p.get("零件") or "") for k in PROCESS_PARTS)])
    return {
        "图纸": 1, "部件承认书": nparts, "UL证明": nparts,
        "材质证明书": nmat, "信赖性": max(1, nparts - 1), "包装": 1, "出货": 1,
    }


# 嵌入组表 全名 → 短名（manifest 用全名，GRID/计数用短名）
SHEET_SHORT = {
    "3.供应商部件承认书": "部件承认书", "8.材质证明书": "材质证明书",
    "9.UL 证明": "UL证明", "6.信赖性测试报告": "信赖性",
}


if __name__ == "__main__":
    import io
    import glob
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    from study.golden_parse import parse_golden
    from study.ole_structure import ole_count_per_sheet

    cases = sorted([p for p in glob.glob(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "案例材料", "承认书", "参考用承诺书集", "*.xlsx"))
        if not os.path.basename(p).startswith("~$")])
    print("计数验证（BOM重算 vs 实测OLE）：")
    cols = ["部件承认书", "UL证明", "材质证明书"]
    ok = miss = 0
    for x in cases:
        code = os.path.basename(x)[:10]
        mats = parse_golden(x)
        pred = embed_group_count(mats)
        act = ole_count_per_sheet(x)
        cells = []
        for c in cols:
            p, a = pred[c], act.get(c, 0)
            mark = "✓" if p == a else f"✗(实{a})"
            cells.append(f"{c}={p}{mark}")
            if p == a:
                ok += 1
            else:
                miss += 1
        print(f"  {code}: " + "  ".join(cells))
    print(f"\n命中 {ok}/{ok+miss}（不中多为源缺，见 YY60039397/38296）")

    # 网格布局自检：8 槽位不重叠
    g = GRID["材质证明书"]
    pos = grid_anchors(8, **g)
    boxes = [(x, y, g["w"], g["h"]) for x, y in pos]
    ov = sum(1 for i in range(8) for j in range(i + 1, 8)
             if not (boxes[i][0] + boxes[i][2] <= boxes[j][0] or boxes[j][0] + boxes[j][2] <= boxes[i][0]
                     or boxes[i][1] + boxes[i][3] <= boxes[j][1] or boxes[j][1] + boxes[j][3] <= boxes[i][1]))
    print(f"\n材质证明书 8 槽位网格布局：{[(x, y) for x, y in pos]}")
    print(f"  重叠对数 = {ov}（应 0），4+4 两行")
