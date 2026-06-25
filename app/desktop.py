# -*- coding: utf-8 -*-
"""确认环① 桌面壳: 子线程跑 uvicorn + pywebview 开窗加载本地 Web。

最终 PyInstaller 打包成单 exe(M3.1)。本地启动: python run_drawing_env.py。
"""
import os
import sys
import time
import threading
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn

HOST, PORT = "127.0.0.1", 8731
URL = f"http://{HOST}:{PORT}/"


def _serve():
    """子线程跑 uvicorn。关信号处理器(非主线程不能装), daemon 随主退出。"""
    server = uvicorn.Server(uvicorn.Config("app.server:app", host=HOST, port=PORT, log_level="warning"))
    server.install_signal_handlers = lambda: None
    server.run()


def start_server(wait=True, timeout=15):
    """启动后端线程; wait=True 时阻塞到 / 可访问。返回是否就绪。"""
    threading.Thread(target=_serve, daemon=True).start()
    if not wait:
        return True
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


def _hold():
    print(f"✅ 后端在 {URL} 运行中 — 关浏览器后 Ctrl+C 退出。")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def launch_browser():
    """起后端 + 默认浏览器打开(可靠兜底; WebView2 缺失/非交互会话黑屏时用)。"""
    import webbrowser
    if not start_server(wait=True):
        print("❌ 后端未在超时内就绪", file=sys.stderr); sys.exit(1)
    webbrowser.open(URL)
    _hold()


def launch(title="久益承认书 · 确认环① 图纸识别"):
    """起后端 + 开 pywebview 窗(主线程)。RUN_BROWSER=1 或 pywebview 异常 → 退回浏览器。"""
    if os.environ.get("RUN_BROWSER"):
        return launch_browser()
    if not start_server(wait=True):
        print("❌ 后端未在超时内就绪", file=sys.stderr); sys.exit(1)
    try:
        import webview
        webview.create_window(title, URL, width=1320, height=860)
        webview.start(gui="edgechromium")          # 强制 WebView2(Chromium), 避退回 MSHTML
    except Exception as e:
        print(f"⚠️ pywebview 启动失败({e}), 退回浏览器", file=sys.stderr)
        import webbrowser
        webbrowser.open(URL)
        _hold()
