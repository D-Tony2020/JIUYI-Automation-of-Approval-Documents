# -*- coding: utf-8 -*-
"""spike 配置：项目路径、锡丝样本文件、国产 LLM provider 端点。

要点：
- Qwen(百炼) 与 GLM(智谱) 均提供 OpenAI 兼容端点，故统一用 openai SDK 调用。
- 调用一律用 trust_env=False 的 httpx client 绕开 Clash 代理（本机踩坑）。
- key 从环境变量读取，未配置则只能用 --provider mock 离线跑。
"""
import os

PROJECT_ROOT = r"D:\Desktop\Moore 工业智能\久益\久益-承认书自动化"
锡丝目录 = os.path.join(PROJECT_ROOT, r"案例材料\承认书\承认书\锡丝")
MSDS_PDF = os.path.join(锡丝目录, "07CU物質安全資料表无铅锡线 Material Safe Data Sheet(1).pdf")
ROHS_PDF = os.path.join(锡丝目录, "锡线ROHS英文版 SZXEC25002243403 2025.06.30.pdf")

# provider -> (base_url, 默认模型, key 环境变量名)
PROVIDERS = {
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-vl-max",            # 也可换 qwen3-vl-plus / qwen-plus
        "key_env": ["DASHSCOPE_API_KEY", "QWEN_API_KEY"],
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4.6v",               # 也可换 glm-4v-plus / glm-4-plus
        "key_env": ["ZHIPUAI_API_KEY", "ZHIPU_API_KEY", "GLM_API_KEY", "BIGMODEL_API_KEY"],
    },
    # 通用中转站(OpenAI兼容聚合网关)：一把 key 路由到 Qwen/GLM/… 只看 model 名。
    # base_url 与 key 走环境变量，model 用 --model 指定。
    "relay": {
        "base_url": os.environ.get("JIUYI_BASE_URL", ""),
        "model": os.environ.get("JIUYI_MODEL", "qwen-plus"),
        "key_env": ["JIUYI_API_KEY"],
    },
}


def get_api_key(provider: str):
    try:                                       # UI 配置优先(%APPDATA%/config.json) → 随包默认 → 环境变量
        from hitl import userdata
        k = userdata.get_api_key()
        if k:
            return k
    except Exception:
        pass
    for env in PROVIDERS[provider]["key_env"]:
        v = os.environ.get(env)
        if v:
            return v
    return None
