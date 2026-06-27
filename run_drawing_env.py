# -*- coding: utf-8 -*-
"""确认环①(图纸识别) 本地启动入口。

  python run_drawing_env.py

需环境变量 DASHSCOPE_API_KEY(官方 qwen 端点, 已持久化到 User 作用域)。
双击启动的桌面壳 = pywebview 开窗加载本地 FastAPI(127.0.0.1:8731)。
"""
import io
import os
import sys

# 冻结 exe 控制台默认 GBK, print 含 ✅/中文 会 UnicodeEncodeError 崩溃 → 全局 UTF-8 兜底(errors=replace)。
if sys.platform == "win32":
    for _s in ("stdout", "stderr"):
        try:
            _f = getattr(sys, _s)
            if _f and getattr(_f, "buffer", None):
                setattr(sys, _s, io.TextIOWrapper(_f.buffer, encoding="utf-8", errors="replace", line_buffering=True))
        except Exception:
            pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.desktop import launch

if __name__ == "__main__":
    launch()
