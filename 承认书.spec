# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包规格 — 久益-承认书自动化 V0.1.0(onedir)。
入口 run_drawing_env.py → app.desktop.launch(pywebview+uvicorn)。
资源(随程序·只读): app/web、hitl/data种子、模板BLANK、spike、study。
写入(运行时): %APPDATA%\\Moore\\久益-承认书自动化(由 hitl.userdata 重定向, 不进包)。
"""
from PyInstaller.utils.hooks import collect_submodules

datas = [
    ("app/web", "app/web"),
    ("hitl/data", "hitl/data"),
    ("模板/承认书空白模板_通用.xlsx", "模板"),
    ("spike", "spike"),
    ("study", "study"),
    ("version.py", "."),
]

hiddenimports = [
    # Windows COM(WPS装配)
    "win32com", "win32com.client", "pythoncom", "pywintypes",
    # uvicorn 运行时动态加载
    "uvicorn.loops.auto", "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto", "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on", "uvicorn.lifespan.off", "uvicorn.logging",
    # PDF/图像/抽取
    "fitz", "pdfplumber", "PIL", "PIL._tkinter_finder",
    # spike 裸名 import(material_extract 运行时 sys.path 插 spike)
    "config", "extract", "assemble", "schemas", "pdf_text",
    # study 命名空间包
    "study.embed_structure", "study.golden_parse", "study.ole_structure", "study.case_data",
    # pywebview(WebView2/edgechromium)
    "webview", "webview.platforms.edgechromium", "clr_loader",
    "version",
]
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("pdfminer")

a = Analysis(
    ["run_drawing_env.py"],
    pathex=[".", "spike"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest", "PyInstaller",
              # 未用的重型库(被PyInstaller自动hook误拉, ~1G+), 显式排除瘦身
              "torch", "torchvision", "torchaudio", "functorch", "transformers",
              "scipy", "sklearn", "pandas", "tensorboard", "cv2", "IPython", "notebook"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="久益承认书自动化",
    console=True,                      # V0.1.0 留控制台便于看错; 稳定后改 False
    icon=None,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    name="久益承认书自动化",
)
