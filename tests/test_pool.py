# -*- coding: utf-8 -*-
"""材料文件池 单测: assert_job 防穿越 + pool 列目录真值与类型概括。"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)


def test_assert_job():
    from app import state
    for ok in ("job_3f9a1c20", "demo403", "m403", "bomtest1", "手测-403"):
        assert state.assert_job(ok), ok
    for bad in ("", "..", "../x", "a/b", "a\\b", "x" * 65):
        assert not state.assert_job(bad), bad


def test_pool_classify(tmp_path, monkeypatch):
    from app import state, server
    job = "demo_pooltest"
    mdir = state.materials_dir(job)
    try:
        for n in ("MSDS-镀锡铜线.pdf", "锡线ROHS英文.pdf", "1061供应商承认书.pdf", "E326510 UL.pdf"):
            open(os.path.join(mdir, n), "w").close()
        r = server.pool(job)
        types = {f["文件"]: f["类型"] for f in r["files"]}
        assert r["count"] == 4
        assert types["MSDS-镀锡铜线.pdf"] == "MSDS(材质源)"
        assert types["锡线ROHS英文.pdf"] == "材质报告(RoHS/REACH/SVHC)"
        assert types["1061供应商承认书.pdf"] == "部件承认书"
        assert types["E326510 UL.pdf"] == "UL"
    finally:
        import shutil
        shutil.rmtree(state.order_dir(job), ignore_errors=True)
