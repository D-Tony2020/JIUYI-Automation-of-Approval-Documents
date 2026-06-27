# -*- coding: utf-8 -*-
"""路径中枢: 资源(随程序·只读) / 运行时(可写) / 用户数据(%APPDATA%·跨重装继承)。

参考久益-标签自动化「全局记忆」: 用户数据脱离安装目录→升级解压新版即用、积累数据自动延续。
- resource_base(): 打包进去的只读资源(模板/hitl-data种子/app-web/spike)。dev=项目根; 冻结=_MEIPASS/exe目录。
- work_base():     运行时工作态(.work/产出留档·可写·不跨重装)。dev=项目根原位; 冻结=%APPDATA%。
- USER_DATA_DIR:   字典学习库(跨重装继承)。恒 %APPDATA%\\Moore\\久益-承认书自动化(缺失→安装目录/userdata 兜底)。
"""
import os
import sys

_FROZEN = getattr(sys, "frozen", False)


def resource_base():
    """只读资源根。冻结→_MEIPASS(onefile)或 exe 目录(onedir); 否则→项目根(hitl/ 上一层)。"""
    if _FROZEN:
        return getattr(sys, "_MEIPASS", None) or os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _install_dir():
    """安装根(冻结时放兜底 userdata): exe 所在, 或其含「模板」的上一层。"""
    if _FROZEN:
        exe = os.path.dirname(sys.executable)
        parent = os.path.dirname(exe)
        return parent if os.path.exists(os.path.join(parent, "模板")) else exe
    return resource_base()


def user_data_dir():
    """跨版本稳定的用户数据目录: %APPDATA%\\Moore\\久益-承认书自动化。
    APPDATA 缺失/不可写(杀软拦截等)→退回 安装目录/userdata, 保证可写(客户机鲁棒)。"""
    appdata = os.environ.get("APPDATA")
    d = (os.path.join(appdata, "Moore", "久益-承认书自动化")
         if (appdata and os.path.isdir(appdata)) else os.path.join(_install_dir(), "userdata"))
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = os.path.join(_install_dir(), "userdata")
        os.makedirs(d, exist_ok=True)
    return d


USER_DATA_DIR = user_data_dir()


def work_base():
    """运行时工作态根(.work 含材料PDF + 产出留档)。WPS COM 要嵌材料PDF、开cell——
    实测 COM 打不开 %APPDATA%(Roaming/Local 都被WPS挡), 能开 Documents/TEMP →
    冻结落「我的文档\\久益承认书自动化」(COM可读 + 用户可见产出); dev→项目根(原位不变)。"""
    if not _FROZEN:
        return resource_base()
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    base = os.path.join(docs if os.path.isdir(docs) else _install_dir(), "久益承认书自动化")
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        base = _install_dir()
    return base
