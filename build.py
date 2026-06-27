# -*- coding: utf-8 -*-
"""打包入口 — 久益-承认书自动化。 用法: python build.py
PyInstaller onedir → dist/久益承认书自动化/久益承认书自动化.exe + _internal/。
用户数据(字典学习库)运行时存 %APPDATA%, 不进包, 重装/升级继承。"""
import io
import os
import shutil
import subprocess
import sys
import time

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from version import VERSION, APP_NAME, BUILD_DATE

DIST = os.path.join(ROOT, "dist")
DEPLOY = """久益-承认书自动化 v%s (%s) — 客户机部署说明
==========================================

【启动】整个文件夹整体拷贝(依赖在 _internal\\, 不能只拷 exe), 双击「久益承认书自动化.exe」。首启稍慢(解压加载~170M)。

【硬性要求(不满足则对应功能不可用)】
 1. Windows 10 / 11, 64 位。
 2. 装有 WPS Office 或 Microsoft Excel —— 导出嵌入报告(OLE)走 COM(优先WPS, 回退Excel)。无则导出失败。
 3. 环境变量 DASHSCOPE_API_KEY —— ①读图纸 + ②读材质 调官方通义千问; 未设置这两步报错。
    设法: 设置→系统→高级系统设置→环境变量→用户变量→新建 DASHSCOPE_API_KEY。
 4. 联网访问 dashscope.aliyuncs.com (HTTPS 443)。默认直连; 走公司代理设 JIUYI_PROXY=http://地址:端口。

【软性(有自动兜底, 不影响功能)】
 5. WebView2 运行时(桌面窗口)。Win11自带; 缺失致黑屏会自动退回默认浏览器。
 6. 写权限: %%APPDATA%%\\Moore\\久益-承认书自动化(字典学习库) + 我的文档\\久益承认书自动化(工作态/产出)。被拦截自动退回安装目录。

【数据与升级】字典学习库存 %%APPDATA%%, 不在安装目录; 升级解压覆盖即继承历史数据。产出在 我的文档\\久益承认书自动化\\产出留档\\。

【可能的提示(非故障)】exe 未签名: SmartScreen 提示"未知发布者"→"仍要运行"; 杀软误报需加白名单。无需另装 Python/依赖。
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
    BUILD_NAME = "久益承认书自动化"                          # = 承认书.spec 的 EXE/COLLECT name(无连字符·文件系统名, 别用APP_NAME含连字符)
    raw = os.path.join(DIST, BUILD_NAME)                     # PyInstaller 产出名
    appdir = os.path.join(DIST, f"{BUILD_NAME}v{VERSION}")   # 版本化发布名(版本管理 + 与历史版并存)
    if os.path.exists(appdir):
        shutil.rmtree(appdir, ignore_errors=True)
    if os.path.exists(raw):
        for _ in range(6):                                  # 杀软/云同步偶尔短暂锁住新建 _internal → 退避重试
            try:
                os.rename(raw, appdir)                       # 重命名为版本目录(确定性, 不依赖外部进程)
                break
            except OSError:
                time.sleep(2)
    try:
        with open(os.path.join(appdir, "部署说明.txt"), "w", encoding="utf-8") as f:
            f.write(DEPLOY)                                  # 写最终目录(修v0.1.0写到改名前旧名→丢失的bug)
    except Exception as e:
        print("写部署说明失败:", e)
    exe = os.path.join(appdir, f"{BUILD_NAME}.exe")
    print(f"\n=== 完成: {exe}  存在={os.path.exists(exe)}  含部署说明={os.path.exists(os.path.join(appdir, '部署说明.txt'))} ===")


if __name__ == "__main__":
    main()
