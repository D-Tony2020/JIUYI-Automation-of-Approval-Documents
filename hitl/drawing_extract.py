# -*- coding: utf-8 -*-
"""A1 段:生图纸 → 品号/版本/名称 + FAI 尺寸(多模态)。

引擎 qwen-vl-max(阿里云 DashScope 官方端点, 红线授权, 在线)。盲测忠实率~100%。
公差归一:VLM 读图纸记法(标称,上,下) → FAI 三列等价(中心, +公差, -公差):
  对称 98±5 → 中心98 ±5; 非对称 35(上0/下3) → 带[32,35] → 中心33.5 ±1.5。
"""
import os, re, json, base64
import fitz
import requests

URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = "qwen3.7-plus"   # 全局统一(实证: vs qwen-vl-max 更快8s/11s + 品号读对 YY 非 YV)

PROMPT = """你是工程图纸尺寸抽取专家。附图是生久公司的产品工程图纸(导线/连接器类),可能含改版履历页+几何主图页。

任务:抽取该产品的【首件检验(FAI)受检尺寸】。优先从图纸的【检查表/检验规格/SPECIFICATION/CTQ/FAI 表格】读取;若无此表,取几何视图上标注的主要功能尺寸(形如 470±8、98±5、1.5±0.5)。

必须排除:
1. 通用公差表/未注公差表(按尺寸段给默认公差的表,如 "0.5~3 ±0.1 / 3~6 ±0.2 / 6~30 ±0.3")
2. 未注角度公差(±1°)、表面处理、材料、净重、比例、PIN脚序号等非受检尺寸

每个尺寸给:标称值、上公差、下公差(对称公差则上下相等),单位mm纯数字。

严格只输出JSON,无任何解释或markdown:
{"品号":"","版本":"","名称":"","FAI尺寸":[{"标称":470,"上":8,"下":8}]}"""


def _render(pdf, dpi=180):
    d = fitz.open(pdf)
    imgs = [pg.get_pixmap(dpi=dpi).tobytes("png") for pg in d]
    d.close()
    return imgs


def _call(images, api_key):
    content = [{"type": "text", "text": PROMPT}]
    for im in images:
        b64 = base64.b64encode(im).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    body = {"model": MODEL, "messages": [{"role": "user", "content": content}],
            "temperature": 0, "max_tokens": 1500}
    if "qwen3" in MODEL:
        body["enable_thinking"] = False         # 结构化抽取关思考(快+JSON干净)
    s = requests.Session(); s.trust_env = False        # 绕 Clash 代理劫持国内API
    r = s.post(URL, headers={"Authorization": f"Bearer {api_key}",
                             "Content-Type": "application/json"}, json=body, timeout=180)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse(txt):
    m = re.search(r"\{.*\}", txt.strip(), re.S)
    return json.loads(m.group(0) if m else txt)


def normalize_tol(nom, up, lo):
    """图纸记法(标称,上公差,下公差) → FAI 等价(中心, +公差, -公差)。

    带 = [标称-下, 标称+上]; 中心 = 带中点; +公差/-公差 = 半带宽(对称化)。
    98,5,5 → (98, 5, 5);  35,0,3 → 带[32,35] → (33.5, 1.5, 1.5)。
    """
    hi, lo_v = nom + up, nom - lo
    ctr = round((hi + lo_v) / 2, 4)
    return ctr, round(hi - ctr, 4), round(ctr - lo_v, 4)


def extract(drawing_pdf, api_key=None):
    """生图纸 → {品号, 版本, 名称, dimensions:[(中心,+公差,-公差)]}。dimensions 可直灌FAI表。"""
    api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY 未设置")
    data = _parse(_call(_render(drawing_pdf), api_key))
    dims = []
    for d in data.get("FAI尺寸", []):
        try:
            dims.append(normalize_tol(float(d["标称"]), float(d["上"]), float(d["下"])))
        except (KeyError, TypeError, ValueError):
            continue
    return {"品号": str(data.get("品号", "")).strip(),
            "版本": str(data.get("版本", "")).strip(),
            "名称": str(data.get("名称", "")).strip(),
            "dimensions": dims}


if __name__ == "__main__":
    import sys, io, glob
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    orders = sorted(glob.glob(os.path.join(root, "本单输入", "pseudo", "*")))
    print(f"=== A1 drawing_extract vs 伪真单真值 ({len(orders)}案) ===\n")
    tot = rec = 0
    for od in orders:
        code = os.path.basename(od)
        gt = json.load(open(os.path.join(od, "_groundtruth.json"), encoding="utf-8"))
        draw = glob.glob(os.path.join(od, "drawing", "*.pdf"))
        if not draw:
            continue
        try:
            r = extract(draw[0])
        except Exception as e:
            print(f"❌ {code}: {str(e)[:80]}"); continue
        true = [(c, t1, t2) for c, t1, t2 in gt["fai"]]
        miss = []
        for (c, t1, t2) in true:
            hit = any(abs(dc - c) < 0.05 and abs(dt1 - t1) < 0.1 and abs(dt2 - t2) < 0.1
                      for dc, dt1, dt2 in r["dimensions"])
            tot += 1; rec += 1 if hit else 0
            if not hit:
                miss.append(f"{c}±({t1}/{t2})")
        flag = "✅" if not miss and true else "❌"
        print(f"{flag} {code}: 品号{r['品号'][:18]} 版本{r['版本']} | "
              f"FAI {len(true)-len(miss)}/{len(true)}{' 缺['+','.join(miss)+']' if miss else ''}")
    print(f"\n===== A1 FAI 归一后召回 {rec}/{tot} ({rec*100//tot if tot else 0}%) =====")
