# -*- coding: utf-8 -*-
"""确认环①(图纸识别) 本地启动入口。

  python run_drawing_env.py

需环境变量 DASHSCOPE_API_KEY(官方 qwen 端点, 已持久化到 User 作用域)。
双击启动的桌面壳 = pywebview 开窗加载本地 FastAPI(127.0.0.1:8731)。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.desktop import launch

if __name__ == "__main__":
    launch()
