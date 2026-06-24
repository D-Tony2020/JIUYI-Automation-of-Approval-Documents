# -*- coding: utf-8 -*-
"""spike 主程序：锡丝一行端到端打穿。

流程：pdftotext 抽两份PDF文本 → LLM抽取(MSDS/RoHS) → 装配JOIN → 对标打分。

用法：
  python run_spike.py --provider mock      # 离线验证流水线(不调API)
  python run_spike.py --provider qwen      # 需 DASHSCOPE_API_KEY
  python run_spike.py --provider glm       # 需 ZHIPUAI_API_KEY
  python run_spike.py --provider qwen --model qwen3-vl-plus
"""
import argparse
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import config
import extract
import score
from assemble import assemble_row
from pdf_text import pdf_to_text, pdf_to_table_markdown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="mock", choices=["mock", "qwen", "glm", "relay"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--deid", action="store_true",
                    help="用去标识化样本(spike/deid/)做模型能力测试，不发送真实客户数据")
    args = ap.parse_args()

    here = os.path.dirname(__file__)
    gt_path = os.path.join(here, "groundtruth.json")

    print(f"[1/4] 准备文本 …")
    if args.deid:
        with open(os.path.join(here, "deid", "msds_deid.txt"), encoding="utf-8") as f:
            msds_text = f.read()
        with open(os.path.join(here, "deid", "rohs_deid.txt"), encoding="utf-8") as f:
            rohs_text = f.read()
        gt_path = os.path.join(here, "deid", "groundtruth_deid.json")
        print(f"      [脱敏模式] MSDS {len(msds_text)} 字符 / RoHS {len(rohs_text)} 字符（不含真实客户身份）")
    elif args.provider == "mock":
        msds_text = rohs_text = "(mock 模式跳过文本抽取)"
    else:
        # 分流：MSDS 窄表走 pdfplumber 表格(避免CAS截断)；第三方报告走 pdftotext 文本层
        msds_text = pdf_to_table_markdown(config.MSDS_PDF) or pdf_to_text(config.MSDS_PDF)
        rohs_text = pdf_to_text(config.ROHS_PDF)
        print(f"      MSDS 表格 {len(msds_text)} 字符 / RoHS 文本 {len(rohs_text)} 字符")

    print(f"[2/4] LLM 抽取 (provider={args.provider}, model={args.model or '默认'}) …")
    msds = extract.extract_msds(msds_text, args.provider, args.model)
    rohs = extract.extract_rohs(rohs_text, args.provider, args.model)
    print("      MSDS 抽取:", json.dumps(msds, ensure_ascii=False)[:160], "…")
    print("      RoHS 抽取:", json.dumps(rohs, ensure_ascii=False)[:160], "…")

    print(f"[3/4] 装配 JOIN（MSDS ⋈ RoHS）→ 材质表一行 …")
    row = assemble_row(msds, rohs, 零件="锡", 材质类别="锡丝", 材质="锡")

    print(f"[4/4] 对标打分 …")
    with open(gt_path, encoding="utf-8") as f:
        gt = json.load(f)
    passed, total = score.print_report(row, gt)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
