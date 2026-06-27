# -*- coding: utf-8 -*-
"""打包入口 — 久益-承认书自动化。 用法: python build.py
PyInstaller onedir → dist/久益承认书自动化/久益承认书自动化.exe + _internal/。
用户数据(字典学习库)运行时存 %APPDATA%, 不进包, 重装/升级继承。"""
import io
import os
import shutil
import subprocess
import sys

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from version import VERSION, APP_NAME, BUILD_DATE

DIST = os.path.join(ROOT, "dist")
DEPLOY = """久益-承认书自动化 v%s (%s)
=====================================
1. 双击「久益承认书自动化.exe」启动(首启稍慢, 后端起来后自动开窗)。
2. 需要环境变量 DASHSCOPE_API_KEY(官方通义千问端点) —— 抽取 MSDS 用。
   若未设置: 系统设置→环境变量→用户变量 新增 DASHSCOPE_API_KEY。
3. 装配承认书需本机装有 WPS 或 Excel(走 COM 嵌 OLE)。
4. 你的字典学习库存在 %%APPDATA%%\\Moore\\久益-承认书自动化 ——
   升级新版(解压覆盖)后数据自动延续, 无需手动迁移。
5. 若窗口黑屏(缺 WebView2): 会自动退回默认浏览器打开。
""" % (VERSION, BUILD_DATE)


def main():
    print(f"=== 打包 {APP_NAME} v{VERSION} ===")
    for d in ("build", "dist"):
        p = os.path.join(ROOT, d)
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "承认书.spec", "--noconfirm", "--clean"],
                       cwd=ROOT)
    if r.returncode != 0:
        print("✗ PyInstaller 失败, 退出码", r.returncode)
        sys.exit(r.returncode)
    appdir = os.path.join(DIST, "久益承认书自动化")
    try:
        with open(os.path.join(appdir, "部署说明.txt"), "w", encoding="utf-8") as f:
            f.write(DEPLOY)
    except Exception as e:
        print("写部署说明失败:", e)
    exe = os.path.join(appdir, "久益承认书自动化.exe")
    print(f"\n=== 完成: {exe}  存在={os.path.exists(exe)} ===")


if __name__ == "__main__":
    main()
