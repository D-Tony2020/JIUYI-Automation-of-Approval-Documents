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
    import time

    cfg = config.PROVIDERS[provider]
    key = config.get_api_key(provider)
    if not key:
        raise RuntimeError(f"未找到 {provider} 的 API key，请设置环境变量之一: {cfg['key_env']}")
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    _model = model or cfg["model"]
    body = {"model": _model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0}
    if "qwen3" in _model.lower():        # qwen3.x 深度思考模型: 结构化抽取关思考(快~5x, 非流式OK, JSON更干净)
        body["enable_thinking"] = False

    # 代理：默认直连(--noproxy *)；JIUYI_PROXY=http://... 则用 -x
    mode = os.environ.get("JIUYI_PROXY", "direct").strip()
    proxy_args = ["-x", mode] if mode.startswith("http") else ["--noproxy", "*"]

    bf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    try:
        json.dump(body, bf, ensure_ascii=False)
        bf.close()
        cmd = ["curl.exe", "-sS", "-m", "90", "--ssl-no-revoke", *proxy_args, url,
               "-H", f"Authorization: Bearer {key}",
               "-H", "Content-Type: application/json",
               "-d", f"@{bf.name}"]
        last = ""
        for attempt in range(3):                       # 重试: 超时/限流多为瞬态
            try:
                out = subprocess.run(cmd, capture_output=True, timeout=100)
            except Exception as e:
                last = f"子进程超时:{e}"; time.sleep(3 + 5 * attempt); continue
            if out.returncode != 0:
                last = f"curl rc={out.returncode}: {out.stderr.decode('utf-8','ignore')[:120]}"
                time.sleep(3 + 5 * attempt); continue
            try:
                data = json.loads(out.stdout.decode("utf-8", "ignore"))
                return _parse_json(data["choices"][0]["message"]["content"])
            except Exception as e:
                last = f"解析失败:{e} 体:{out.stdout.decode('utf-8','ignore')[:120]}"
                time.sleep(2); continue
        raise RuntimeError(last)
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
