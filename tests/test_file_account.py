# -*- coding: utf-8 -*-
"""覆盖审计红线: 每个上传文件都有主(全集=已放置∪待归位∪排除, 两两不交)。
重点回归: route=∅(未识别)、豁免材质的文件、操作员排除/横排指派 都不丢。"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from hitl.file_account import account_files
from hitl.file_router import route


def _mk(d, *names):
    for n in names:
        open(os.path.join(d, n), "w", encoding="utf-8").close()


def _invariant(acc):
    return acc["total"] == len(acc["placed"]) + len(acc["pending"]) + len(acc["excluded"])


def test_route空文件确实未识别():
    assert route("C2001&C2002(51005&51006).pdf") == set()      # 复现根因: 纯料号→route∅


def test_未识别文件入待归位不丢(tmp_path):
    d = str(tmp_path)
    _mk(d, "镀锡线REACH CANEC.pdf", "MSDS-镀锡铜线.pdf", "C2001&C2002(51005&51006).pdf")
    materials = [{"材质": "镀锡铜", "files": {"MSDS": "MSDS-镀锡铜线.pdf",
                  "REACH": ["镀锡线REACH CANEC.pdf"], "RoHS": [], "SVHC": [], "其他": []}}]
    acc = account_files(d, materials)
    assert "C2001&C2002(51005&51006).pdf" in acc["pending"]   # route=∅→pending(不再静默丢)
    assert "MSDS-镀锡铜线.pdf" in acc["placed"]
    assert "镀锡线REACH CANEC.pdf" in acc["placed"]
    assert _invariant(acc) and acc["total"] == 3


def test_豁免材质的文件不跟着豁免_入待归位(tmp_path):
    d = str(tmp_path)
    _mk(d, "PVC MSDS.pdf", "PVC-REACH.pdf")
    materials = [{"材质": "PVC", "豁免": True, "files": {"MSDS": "PVC MSDS.pdf",
                  "REACH": ["PVC-REACH.pdf"], "RoHS": [], "SVHC": [], "其他": []}}]
    acc = account_files(d, materials)
    assert "PVC MSDS.pdf" in acc["pending"]               # 红线: 豁免≠文件豁免
    assert "PVC-REACH.pdf" in acc["pending"]
    assert not acc["placed"] and _invariant(acc)


def test_横排手动指派route空文件_算已放置(tmp_path):
    d = str(tmp_path)
    _mk(d, "C2001&C2002.pdf")
    acc = account_files(d, [], 部件归属={"C2001&C2002.pdf": {"槽": "部件承认", "零件": "导线"}})
    assert "C2001&C2002.pdf" in acc["placed"] and not acc["pending"]


def test_排除文件入excluded(tmp_path):
    d = str(tmp_path)
    _mk(d, "junk.pdf")
    acc = account_files(d, [], excluded_files=[{"文件": "junk.pdf", "原因": "误传"}])
    assert "junk.pdf" in acc["excluded"] and not acc["pending"] and _invariant(acc)


def test_route命中横排固定位_算已放置(tmp_path):
    d = str(tmp_path)
    _mk(d, "1007系列 承认书(1).pdf", "JY-SOP-P0600 包 装.pdf", "YY 出货检验报告.pdf")
    acc = account_files(d, [])
    for f in ("1007系列 承认书(1).pdf", "JY-SOP-P0600 包 装.pdf", "YY 出货检验报告.pdf"):
        assert f in acc["placed"]
    assert not acc["pending"] and _invariant(acc)
