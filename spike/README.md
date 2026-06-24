# Spike：锡丝一行端到端打穿

验证"基于生久图纸自动生成承认书"里**最核心、最难的一环**——材质成分表一行的自动抽取与装配——在最干净的样本（锡丝，4 文件）上是否可行，并据此选型国产 LLM。

## 这条链路覆盖了全产品的核心难点
- **跨文件 JOIN**：MSDS(成份/CAS/重量%) ⋈ RoHS报告(十项/编号/日期)，无单文件自足。
- **ND vs 具体数值**：Pb=63ppm 非 ND，必须照填（陷阱）。
- **三种单位/格式换算**：wt%→小数(99.3→0.993)、英文日期(Jun 30,2025→2025.06.30)、mg/kg=ppm。
- **供应商名归一**：興鴻泰錫業/深圳市兴鸿泰锡业/XING HONG TAI → 兴鸿泰。

## 跑法
```bash
# 离线验证流水线（不调API，已通过 19/19=100%）
python run_spike.py --provider mock

# 接国产 LLM 实测（需先配 key）
set DASHSCOPE_API_KEY=xxx   &&  python run_spike.py --provider qwen           # 通义千问
set ZHIPUAI_API_KEY=xxx     &&  python run_spike.py --provider glm            # 智谱GLM
python run_spike.py --provider qwen --model qwen3-vl-plus                     # 指定模型
```

## 关键工程结论（spike 实测所得）
1. **抽取策略必须按文档类型分流**：
   - 第三方报告(SGS/CTI RoHS)：`pdftotext -layout` 文本层干净、报告号/日期/Pb=63 全部可读，零乱码。
   - 自制 MSDS(窄列表格)：`pdftotext` 会把 CAS 末位换行截断（7440-31-5→7440-31-）；改用 `pdfplumber` 表格模式可完整恢复（含多余空格，由 `assemble.normalize_cas` 修复）。性能优先时亦可直接把该页栅格化(fitz)喂视觉模型。
   - **切勿用 fitz/PyMuPDF 抽中文文本**（勘测已证乱码）。
2. **确定性后处理(assemble.py)** 承载已确认的填写规则：重量% 小数化+'余量'/'<3'原样、RoHS 'N.D.'归一+非ND照填、日期归一、供应商别名归一。
3. **report_number / date 可直接由文件名匹配**，无需读正文（最易字段）。

## 文件
| 文件 | 职责 |
|---|---|
| run_spike.py | 主程序：抽文本→LLM抽取→装配→打分 |
| pdf_text.py | pdftotext文本层 / pdfplumber表格 / fitz栅格化 |
| schemas.py | MSDS、RoHS 抽取 schema + prompt（核心IP） |
| extract.py | LLM调用层（mock/qwen/glm，trust_env=False绕代理） |
| assemble.py | 装配JOIN + 单位换算 + CAS修复 + 供应商归一 |
| score.py / groundtruth.json | 对标标准答案打分 |
| mock/*.json | 离线模拟抽取输出（含被截断CAS、英文日期等真实陷阱） |

## 实测结果（2026-06-21，经 aiapi.world 中转站，脱敏样本 spike/deid/）
| 模型 | 准确率 |
|---|---|
| **qwen3.7-plus** | **19/19 = 100%** |
| **glm-5.2** | **19/19 = 100%** |

两家都正确处理了全部硬陷阱：繁体成份名、被截断 CAS、**Pb=63 非 ND**、英文日期、wt%→小数。结论：**国产旗舰 LLM 抽取能力足够**。

### 过程中的工程结论（重要）
- **不要用 httpx/openai SDK 调这个中转站**：对 chat 接口会莫名挂死(300s+)、读超时拦不住；**改走 `curl.exe -m` 子进程**（同请求 5s 返回，墙钟硬超时可靠）。见 extract.py。
- **prompt 必须内嵌确切 JSON 键名模板**：否则模型自创键名(supplier_name/中文键)，assemble 取空(首测仅 3/19)。修正后 18→19。
- **MSDS 成分列恒为百分数**：normalize_weight 一律 ÷100（曾因 0.7<1 未除导致 Cu 错）。
- **数据边界**：真实客户 PDF 经第三方中转站发送会被安全闸拦截；本 spike 用**手造脱敏样本**(deid/，无客户身份)验证模型能力，真实数据须本地/官方端点跑。

## 待办
- [ ] 平移到更难样本：线材(正崴，含**扫描件**金印铜业MSDS→走视觉模型)、端子(联和，磷青铜多元素)、套管(领飞，**磷系/氮系阻燃剂冲突**→标红人工裁决)。
- [ ] 用**真实 PDF**（本地或官方端点）跑一遍，验证 pdfplumber/pdftotext 真实脏输出下的鲁棒性。
- [ ] 接入视觉模型路径（qwen3-vl / glm 视觉）处理扫描件。
