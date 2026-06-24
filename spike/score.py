# -*- coding: utf-8 -*-
"""打分层：把装配出的材质表一行与标准答案逐字段比对，输出准确率。"""
import json
import os

from schemas import ROHS_KEYS


def load_groundtruth():
    path = os.path.join(os.path.dirname(__file__), "groundtruth.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _cmp(a, b):
    return str(a).strip() == str(b).strip()


def score_row(row: dict, gt: dict):
    checks = []  # (字段, 期望, 实得, 是否通过)

    for f in ["零件", "材质类别", "材质", "原材料供应商", "检测报告编号", "检测报告日期"]:
        checks.append((f, gt.get(f), row.get(f), _cmp(gt.get(f), row.get(f))))

    # 成份逐项（按 CAS 对齐）
    gt_comp = {c["CAS"]: c for c in gt.get("成份", [])}
    row_comp = {c["CAS"]: c for c in row.get("成份", [])}
    for cas, gc in gt_comp.items():
        rc = row_comp.get(cas)
        ok = rc is not None and _cmp(gc["重量%"], rc.get("重量%"))
        checks.append((f"成份[{gc['成份名称']}/{cas}].重量%", gc["重量%"],
                       rc.get("重量%") if rc else "(缺)", ok))

    # RoHS 十项
    for k in ROHS_KEYS:
        checks.append((f"RoHS.{k}", gt["RoHS"][k], row["RoHS"].get(k), _cmp(gt["RoHS"][k], row["RoHS"].get(k))))

    passed = sum(1 for *_, ok in checks if ok)
    return checks, passed, len(checks)


def print_report(row, gt):
    checks, passed, total = score_row(row, gt)
    print("\n================ 材质表一行 · 装配结果 ================")
    print(json.dumps(row, ensure_ascii=False, indent=2))
    print("\n================ 逐字段对标 ================")
    for field, exp, got, ok in checks:
        mark = "✅" if ok else "❌"
        print(f"  {mark} {field:<28} 期望={exp!s:<14} 实得={got!s}")
    pct = passed / total * 100 if total else 0
    print(f"\n>>> 准确率: {passed}/{total} = {pct:.1f}%")
    return passed, total
