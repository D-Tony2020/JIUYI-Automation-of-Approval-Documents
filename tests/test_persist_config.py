# -*- coding: utf-8 -*-
"""跨设备持久化 + API key 配置。

回归: 本机 %APPDATA%\\Moore 被 OneDrive 重定向到别的卷, os.replace(tmp,dst) 报 WinError17,
导致学习库/配置静默不落盘(无监督命中命脉断)。atomic_write_json 必须在此退回直接写。
旧测全都 monkeypatch 到本地盘 tmp_path → os.replace 成功 → 永远测不出这个坑, 故专测。
"""
import os
import json
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from hitl import userdata, dicts


def _force_crossdevice(monkeypatch):
    def boom(a, b):
        raise OSError(17, "系统无法将文件移到不同的磁盘驱动器(模拟OneDrive重定向)")
    monkeypatch.setattr(os, "replace", boom)


def test_atomic_write_跨设备退回直接写(tmp_path, monkeypatch):
    _force_crossdevice(monkeypatch)
    p = str(tmp_path / "sub" / "x.json")
    userdata.atomic_write_json(p, {"k": "值"})
    assert json.load(open(p, encoding="utf-8"))["k"] == "值"   # os.replace失败仍落盘
    assert not os.path.exists(p + ".tmp")                       # 残留tmp已清


def test_dicts学习库跨设备仍持久化(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    _force_crossdevice(monkeypatch)
    dicts._save("category", {"导线(黄)": "导线"})
    assert dicts._load("category", {}) == {"导线(黄)": "导线"}   # OneDrive机上 learn 仍落盘=无监督命中不丢


def test_api_key_配置优先于环境变量与默认(tmp_path, monkeypatch):
    monkeypatch.setattr(userdata, "USER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(userdata, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(userdata, "_DEFAULT_KEY_FILE", str(tmp_path / "_none.txt"))
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    assert userdata.get_api_key() == ""                        # 啥都没配
    userdata.set_api_key("sk-ui")
    assert userdata.get_api_key() == "sk-ui"                    # UI填写生效
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-env")
    assert userdata.get_api_key() == "sk-ui"                    # 配置优先于环境变量
    userdata.set_api_key("")
    assert userdata.get_api_key() == "sk-env"                   # 清空→回退环境变量


def test_api_key_随包默认兜底(tmp_path, monkeypatch):
    monkeypatch.setattr(userdata, "USER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(userdata, "CONFIG_PATH", str(tmp_path / "config.json"))
    keyfile = tmp_path / "_api_key.txt"
    keyfile.write_text("sk-bundled\n", encoding="utf-8")
    monkeypatch.setattr(userdata, "_DEFAULT_KEY_FILE", str(keyfile))
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    assert userdata.get_api_key() == "sk-bundled"              # 无用户配置→随包默认(strip换行)
