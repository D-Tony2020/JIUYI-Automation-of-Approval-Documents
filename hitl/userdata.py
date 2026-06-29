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

# ── 应用配置(API key 等): 存 %APPDATA%/config.json(UI可改·跨重装继承), 取消强制环境变量 ──
CONFIG_PATH = os.path.join(USER_DATA_DIR, "config.json")
_DEFAULT_KEY_FILE = os.path.join(resource_base(), "hitl", "data", "_api_key.txt")  # 随包默认(gitignore·不入库)


def atomic_write_json(path, data):
    """写 JSON。优先原子写(临时文件+os.replace)防写一半坏档; 但 os.replace 跨设备报 WinError17——
    本机 %APPDATA%\\Moore 被 OneDrive 重定向到别的卷, rename 即跨设备→退回直接覆盖写(放弃原子性,
    远比静默丢数据强)。学习库/配置持久化都走这里(否则 OneDrive 机上学习/保存全部静默失败)。"""
    import json
    text = json.dumps(data, ensure_ascii=False, indent=1)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError:
        with open(path, "w", encoding="utf-8") as f:   # 跨设备/重定向 → 直接写
            f.write(text)
        try:
            os.remove(tmp)
        except OSError:
            pass


def _load_config():
    import json
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_api_key():
    """官方通义/DashScope key 取值优先级: 用户配置(%APPDATA%/config.json) → 随包默认 → 环境变量。
    不再强制操作员设环境变量——UI 直接填即可(见 set_api_key)。"""
    k = (_load_config().get("api_key") or "").strip()
    if k:
        return k
    try:
        with open(_DEFAULT_KEY_FILE, encoding="utf-8") as f:
            k = (f.read() or "").strip()
            if k:
                return k
    except Exception:
        pass
    for env in ("DASHSCOPE_API_KEY", "QWEN_API_KEY"):
        v = os.environ.get(env)
        if v:
            return v
    return ""


def set_api_key(k):
    """UI 保存 API key → 写 %APPDATA%/config.json(跨设备安全写)。"""
    cfg = _load_config()
    cfg["api_key"] = str(k or "").strip()
    try:
        atomic_write_json(CONFIG_PATH, cfg)
    except OSError:
        pass
    return cfg["api_key"]


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
