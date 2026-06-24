# -*- coding: utf-8 -*-
"""抽取层：把 PDF 文本喂给国产 LLM（Qwen/GLM），强约束输出 JSON。

- provider=mock：读 mock/*.json，离线验证流水线（不调 API）。
- provider=qwen/glm：用 openai SDK 调 OpenAI 兼容端点，trust_env=False 绕代理。
"""
import json
import os
import re

import config


def _load_mock(name: str):
    path = os.path.join(os.path.dirname(__file__), "mock", name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _parse_json(text: str):
    """从模型回复里抠出 JSON（容忍 ```json 包裹或前后噪声）。"""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("模型未返回可解析 JSON:\n" + text[:500])
    return json.loads(m.group(0))


def _call_llm(provider: str, prompt: str, model: str = None) -> dict:
    """经 curl.exe 子进程调用 OpenAI 兼容端点。

    放弃 httpx/openai SDK：实测它对中转站 chat 接口会莫名挂死(300s+)、读超时拦不住；
    curl 同请求 5s 返回且 -m 是墙钟硬超时，可靠。
    """
    import subprocess
    import tempfile

    cfg = config.PROVIDERS[provider]
    key = config.get_api_key(provider)
    if not key:
        raise RuntimeError(f"未找到 {provider} 的 API key，请设置环境变量之一: {cfg['key_env']}")
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    body = {"model": model or cfg["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0}

    # 代理：默认直连(--noproxy *)；JIUYI_PROXY=http://... 则用 -x
    mode = os.environ.get("JIUYI_PROXY", "direct").strip()
    proxy_args = ["-x", mode] if mode.startswith("http") else ["--noproxy", "*"]

    bf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    try:
        json.dump(body, bf, ensure_ascii=False)
        bf.close()
        cmd = ["curl.exe", "-sS", "-m", "120", *proxy_args, url,
               "-H", f"Authorization: Bearer {key}",
               "-H", "Content-Type: application/json",
               "-d", f"@{bf.name}"]
        out = subprocess.run(cmd, capture_output=True, timeout=130)
        if out.returncode != 0:
            raise RuntimeError(f"curl rc={out.returncode}: {out.stderr.decode('utf-8','ignore')[:200]}")
        data = json.loads(out.stdout.decode("utf-8", "ignore"))
        if "choices" not in data:
            raise RuntimeError(f"接口返回异常: {str(data)[:300]}")
        return _parse_json(data["choices"][0]["message"]["content"])
    finally:
        os.unlink(bf.name)


def extract_msds(text: str, provider: str, model: str = None) -> dict:
    if provider == "mock":
        return _load_mock("msds_extract.json")
    from schemas import MSDS_PROMPT
    return _call_llm(provider, MSDS_PROMPT.replace("{TEXT}", text), model)


def extract_rohs(text: str, provider: str, model: str = None) -> dict:
    if provider == "mock":
        return _load_mock("rohs_extract.json")
    from schemas import ROHS_PROMPT
    return _call_llm(provider, ROHS_PROMPT.replace("{TEXT}", text), model)
