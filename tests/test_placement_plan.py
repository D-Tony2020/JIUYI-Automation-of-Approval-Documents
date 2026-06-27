# -*- coding: utf-8 -*-
"""M2.4 放置引擎 hitl/placement_plan 单测(纯位置, 零 COM)。

锁: 扁平→嵌套分组+材质类别合并+ordered同序; 材质表证据列K/L/Y; 无同格重叠;
    mat_idx 对齐 compute_layout 行; 材质证明一材一份。
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from hitl.material_table import compute_layout, OLE_COL
from hitl.placement_plan import stage2_to_nested_bom, material_specs, expected_slots

SHEETS = ["封面", "7.材质成分展开表 ", "8.材质证明书", "3.供应商部件承认书"]

STAGE2 = {
    "_sheet_names": SHEETS,
    "materials": [
        {"零件": "导线", "材质": "PVC", "材质类别": "线材", "供应商": "金霖",
         "成份": [{"成份名称": "a", "CAS": "1-1-1", "重量%": "0.5"}], "RoHS": {}, "报告编号": "R1",
         "files": {"MSDS": "PVC.pdf", "RoHS": ["PVC_ROHS.pdf"], "REACH": [], "SVHC": [], "其他": []}},
        {"零件": "导线", "材质": "镀锡铜", "材质类别": "线材", "供应商": "金元",
         "成份": [{"成份名称": "Cu", "CAS": "7440-50-8", "重量%": "0.99"},
                {"成份名称": "Sn", "CAS": "7440-31-5", "重量%": "0.01"}], "RoHS": {}, "报告编号": "R2",
         "files": {"MSDS": "DXT.pdf", "RoHS": ["DXT_ROHS.pdf"], "REACH": ["DXT_REACH.pdf"], "SVHC": [], "其他": []}},
        {"零件": "端子", "材质": "磷铜", "材质类别": "端子", "供应商": "联和",
         "成份": [{"成份名称": "Cu", "CAS": "7440-50-8", "重量%": "0.9"}], "RoHS": {}, "报告编号": "R3",
         "files": {"MSDS": "LT.pdf", "RoHS": [], "REACH": [], "SVHC": [], "其他": []}},
    ],
}


def test_豁免材质不进装表():
    mats = [{"零件": "导线", "材质": "PVC", "files": {}},
            {"零件": "导线", "材质": "白墨重复", "豁免": True, "files": {}},   # 合并的重复→豁免
            {"零件": "导线", "材质": "镀锡铜", "files": {}}]
    nested, ordered = stage2_to_nested_bom(mats)
    名 = [m["材质"] for p in nested for m in p["materials"]]
    assert "白墨重复" not in 名 and 名 == ["PVC", "镀锡铜"]      # 豁免排除, 不进材质表
    assert len(ordered) == 2                                  # ordered 同步排除(mat_idx 不错位)


def test_assign_parts_for分配():
    from hitl.placement_plan import assign_parts_for
    mats = [{"零件": "导线", "材质": "PVC", "材质类别": "线材"},
            {"零件": "热缩管", "材质": "聚烯烃", "材质类别": "套管", "源文件": "环保热缩套管MSDS.pdf"}]
    r = assign_parts_for(["四川领飞热缩套管承认书.pdf", "1061系列承认书.pdf"], mats, ["导线", "热缩管"])
    assert r["四川领飞热缩套管承认书.pdf"] == "热缩管"   # 内容匹配(热缩套管token)
    assert r["1061系列承认书.pdf"] == "导线"            # 推不出→补剩余采购部件(按序)


def test_part_category部件类别标签():
    from hitl.placement_plan import _part_category
    mats = [{"零件": "导线", "材质类别": "线材"}, {"零件": "导线", "材质类别": "线材"},
            {"零件": "胶座端子", "材质类别": "胶座"}, {"零件": "胶座端子", "材质类别": "端子"},
            {"零件": "热缩管", "材质类别": "套管"}, {"零件": "导线", "材质类别": "线材", "豁免": True}]
    cat = _part_category(mats)
    assert cat["导线"] == "线材"                 # 同类别去重
    assert cat["胶座端子"] == "胶座端子"          # 多类别拼接(胶座+端子)
    assert cat["热缩管"] == "套管"


def test_同零件内材质拖序传递装表():
    mats = [{"零件": "导线", "材质": "PVC", "files": {}}, {"零件": "导线", "材质": "镀锡铜", "files": {}},
            {"零件": "导线", "材质": "白墨", "files": {}}]
    nested, _ = stage2_to_nested_bom(mats)
    assert [m["材质"] for m in nested[0]["materials"]] == ["PVC", "镀锡铜", "白墨"]   # 同零件内=数组序
    mats2 = [mats[2], mats[0], mats[1]]                                          # 拖动: 白墨提到首
    nested2, ordered2 = stage2_to_nested_bom(mats2)
    assert [m["材质"] for m in nested2[0]["materials"]] == ["白墨", "PVC", "镀锡铜"]  # 装表跟随新序
    assert [m["材质"] for m in ordered2] == ["白墨", "PVC", "镀锡铜"]                # OLE mat_idx 同步


def test_拖动改材质归属传递装表():
    # 模拟③把"镀锡铜"从导线拖到端子(moveMatToPart 改 零件) → 装表分组须跟随
    mats = [{"零件": "导线", "材质": "PVC", "files": {}},
            {"零件": "导线", "材质": "镀锡铜", "files": {}}]
    mats[1]["零件"] = "端子"                                  # 拖动后的状态
    nested, ordered = stage2_to_nested_bom(mats, part_order=["导线", "端子"])
    名 = {p["零件"]: [m["材质"] for m in p["materials"]] for p in nested}
    assert 名 == {"导线": ["PVC"], "端子": ["镀锡铜"]}        # 镀锡铜归属变端子, 材质表/OLE 跟随
    assert [m["材质"] for m in ordered] == ["PVC", "镀锡铜"]  # ordered 同序(mat_idx 对齐不错位)


def test_part_order_显式排序():
    mats = [{"零件": "锡", "材质": "锡", "files": {}}, {"零件": "导线", "材质": "PVC", "files": {}}]
    nested, ordered = stage2_to_nested_bom(mats, part_order=["导线", "锡"])
    assert [p["零件"] for p in nested] == ["导线", "锡"]      # 按 part_order, 非首现序(锡在前)
    assert [m["材质"] for m in ordered] == ["PVC", "锡"]      # ordered 同步(mat_idx 对齐)


def test_part_order_序外保首现():
    mats = [{"零件": "X", "材质": "a", "files": {}}, {"零件": "导线", "材质": "b", "files": {}},
            {"零件": "Y", "材质": "c", "files": {}}]
    nested, _ = stage2_to_nested_bom(mats, part_order=["导线"])
    assert [p["零件"] for p in nested] == ["导线", "X", "Y"]  # 导线提前, X/Y 保首现序


def test_嵌套分组保序():
    nested, ordered = stage2_to_nested_bom(STAGE2["materials"])
    assert [p["零件"] for p in nested] == ["导线", "端子"]
    assert [len(p["materials"]) for p in nested] == [2, 1]
    assert [m["材质"] for m in ordered] == ["PVC", "镀锡铜", "磷铜"]


def test_材质类别每材质保留不坍缩():
    nested, _ = stage2_to_nested_bom(STAGE2["materials"])
    导线 = nested[0]["materials"]
    assert 导线[0]["材质类别"] == "线材" and 导线[1]["材质类别"] == "线材"   # 不坍缩: 各保自己类别
    assert nested[1]["materials"][0]["材质类别"] == "端子"


def test_ordered序等于compute_layout展开序():
    nested, ordered = stage2_to_nested_bom(STAGE2["materials"])
    expand = [m["材质"] for p in nested for m in p["materials"]]
    assert [m["材质"] for m in ordered] == expand


def test_一材一块():
    nested, _ = stage2_to_nested_bom(STAGE2["materials"])
    for p in nested:
        for m in p["materials"]:
            assert len(m["blocks"]) == 1
    # 镀锡铜 块含 2 成份
    assert len(nested[0]["materials"][1]["blocks"][0]["成份"]) == 2


def test_材质表证据列KLY():
    specs, _, _ = material_specs(STAGE2, "matdir")
    mt = [s for s in specs if s["short"] == "材质表"]
    bycol = {}
    for s in mt:
        bycol.setdefault(os.path.basename(s["pdf"]), s["col"])
    assert bycol["PVC.pdf"] == OLE_COL["MSDS"] and bycol["PVC_ROHS.pdf"] == OLE_COL["RoHS"]
    assert bycol["DXT_REACH.pdf"] == OLE_COL["REACH"]          # REACH→L
    assert bycol["DXT_ROHS.pdf"] == OLE_COL["RoHS"]            # RoHS→Y


def test_材质表无同格重叠():
    specs, _, _ = material_specs(STAGE2, "matdir")
    cells = [(s["row"], s["col"]) for s in specs if s["short"] == "材质表"]
    assert len(cells) == len(set(cells))                       # 每证据独占一格


def test_mat_idx对齐compute_layout行():
    specs, nested, ordered = material_specs(STAGE2, "matdir")
    layout = compute_layout(nested)
    mat_first = [M["blocks"][0]["first"] for P in layout["parts"] for M in P["materials"]]
    msds = {os.path.basename(s["pdf"]): s["row"] for s in specs
            if s["short"] == "材质表" and s["col"] == OLE_COL["MSDS"]}
    assert msds["PVC.pdf"] == mat_first[0]                     # PVC 落自己的块首行
    assert msds["DXT.pdf"] == mat_first[1]
    assert msds["LT.pdf"] == mat_first[2]
    assert mat_first[0] < mat_first[1] < mat_first[2]          # 三材质行递增不撞


def test_材质证明一材一份():
    specs, _, ordered = material_specs(STAGE2, "matdir")
    cert = [s for s in specs if s["short"] == "材质证明"]
    assert len(cert) == 3                                      # 每材质 MSDS 一份证明
    assert {os.path.basename(s["pdf"]) for s in cert} == {"PVC.pdf", "DXT.pdf", "LT.pdf"}


def test_缺证据不硬塞():
    # 磷铜无 RoHS/REACH → 材质表只 1 个 spec(MSDS)
    specs, _, _ = material_specs(STAGE2, "matdir")
    lt = [s for s in specs if s["short"] == "材质表" and "LT" in s["pdf"]]
    assert len(lt) == 1 and lt[0]["col"] == OLE_COL["MSDS"]


def test_expected_slots():
    nested, _ = stage2_to_nested_bom(STAGE2["materials"])
    slots = expected_slots(nested)
    assert slots["材质证明书"] == 3                            # 一材一证
    assert slots["部件承认书"] == 2                            # 采购件=导线+端子(无工艺料锡)


def test_同名报告REACH_SVHC双挂去重(tmp_path):
    # 一文件同时挂 REACH+SVHC(同物理L列) → 材质表只生成1个OLE(去重), 不再2个重叠
    from hitl.placement_plan import build_specs
    sheets = ["7材质成分展开表", "8材质证明书"]
    stage = {"materials": [{"材质": "PVC", "零件": "导线", "材质类别": "线材",
                            "files": {"MSDS": "PVC.pdf", "REACH": ["X.pdf"], "SVHC": ["X.pdf"]}}],
             "_sheet_names": sheets}
    specs, _, _ = build_specs(stage, sheets, str(tmp_path))
    l = [s for s in specs if s.get("short") == "材质表" and s.get("col") == 12]
    assert len(l) == 1                                   # X.pdf 双挂→只1个L列OLE


def test_真双份REACH_dup横向错开(tmp_path):
    from hitl.placement_plan import build_specs
    sheets = ["7材质成分展开表", "8材质证明书"]
    stage = {"materials": [{"材质": "PVC", "零件": "导线", "材质类别": "线材",
                            "files": {"MSDS": "PVC.pdf", "REACH": ["红.pdf", "黑.pdf"]}}],
             "_sheet_names": sheets}
    specs, _, _ = build_specs(stage, sheets, str(tmp_path))
    l = sorted([s for s in specs if s.get("short") == "材质表" and s.get("col") == 12], key=lambda s: s.get("dup", 0))
    assert len(l) == 2 and l[0]["dup"] == 0 and l[1]["dup"] == 1 and l[0]["row"] == l[1]["row"]   # 同行+dup错开


def test_材质证明组首张带部件标签(tmp_path):
    from hitl.placement_plan import build_specs
    sheets = ["7材质成分展开表", "8材质证明书"]
    stage = {"materials": [
        {"材质": "镀锡铜", "零件": "导线", "材质类别": "线材", "files": {"MSDS": "a.pdf"}},
        {"材质": "PVC", "零件": "导线", "材质类别": "线材", "files": {"MSDS": "b.pdf"}},
        {"材质": "PA66", "零件": "胶座端子", "材质类别": "胶座", "files": {"MSDS": "c.pdf"}}],
        "_sheet_names": sheets}
    specs, _, _ = build_specs(stage, sheets, str(tmp_path))
    tags = [s.get("部件标签", "") for s in specs if s.get("short") == "材质证明"]
    assert tags == ["线材", "", "胶座"]                  # 导线组首张标·次张空; 胶座端子组首张标
