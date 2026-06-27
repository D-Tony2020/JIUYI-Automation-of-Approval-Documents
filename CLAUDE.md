# 久益-承认书自动化 — AI 入职手册（项目级）

> 你（Claude Code）进入本仓必读。公司级手册见上级目录 `Moore 工业智能/CLAUDE.md`（角色/看板/红线）；本文件只讲**这个产品**。
> ⚠️ 本仓是工作副本 `久益-承认书自动化-HITL`。**别碰隔壁无后缀 `久益-承认书自动化/` 的 `renshu/` 旧结构**——那不是本项目代码（Explore agent 多次漂过去，警惕）。

---

## 1. 一句话定位 + 客户原始业务流

**久益**（连接器/线束供应商）给客户**生久**供货。生久要求：**新零件首次供货质量准入**前，久益必须交一本 **15 表《材料承认书》（生久 Rev3.1）**——含 BOM 材质成分、有害物质(RoHS/REACH)、FAI 全尺寸、各类报告(MSDS/UL/信赖性)、样品照片，且报告以 **OLE 对象**嵌进 Excel（可双击打开源 PDF）。

**久益现状**：**半自动**——有 Excel 模板，但 BOM/成分/报告/OLE 全靠操作员**手填手嵌**，耗时易错。**本产品就是自动化这套半手工流程**。锚案：`YY60039403`（导线+胶座端子+热缩管+锡，8 材质）。

**承认书结构**（材质成分展开表 A–V 列是核心）：A项次 B零件 C原材料供货商 D材质类别 E材质 F重量 G成份名 H CAS J重量% | K MSDS / L REACH·SVHC / Y RoHS报告（这三列嵌 OLE）| M–V RoHS十项。其他 OLE 表：材质证明书/部件承认书/UL证明/信赖性/图纸/包装/出货。

---

## 2. 本产品用户流（5 步流 + 两确认环）

本地 Web GUI，5 步顺序流，前 4 步是"识别/确认层"(嵌入前)，第 5 步导出(段二 COM 嵌 OLE)：

| 步 | 页面 | 干什么 |
|---|---|---|
| **①核对图纸** | `index.html` | qwen-vl 多模态读图纸 → 抽 品号/版本/FAI 尺寸 → 操作员**复核纠正**(±公差归一)→确认 |
| ②选型 | (折叠/最小) | 供应商选型；当前并入③ |
| **③BOM脊柱** | `index_bom.html` | **材质为锚**(见§5)：上传材料 PDF 堆→B 提议材质→改材质名(字典 resolve 出标准名+类别/零件)→零件级供应商→成分核对→放行 |
| **④文件树** | `index_filetree.html` | 确认每证据文件落哪表哪格(材质表 K/L/Y、材质证明/部件/UL…)；拖拽纠正"认不准"的报告；空槽提示；豁免 |
| **⑤照片+导出** | `index_export.html` | 剪贴板贴样品照片→导出预检(全软预警勾已知悉)→**段二 COM 嵌 OLE**→终态承认书.xlsx + 开目录/下载 |

跨页自动跳转(`?job=` 带 job)。`②选型` 步条在但未独立成页。

---

## 3. 架构与两段装配

- **本地 Web**：`app/server.py`(FastAPI 薄端点) + `app/web/`(原生 JS 前端，无框架) + `app/desktop.py`(pywebview edgechromium / 浏览器兜底)。运行态在 `.work/orders/<job>/`：`stage1_drawing.json`(①) / `stage2_bom.json`(③) / `stage3_filetree.json`(④) / `project.json`(step) + `drawing/ materials/ photos/`。
- **段一 openpyxl 填格**：`hitl/build.py:build_upto` → 各表 fill；材质表 `material_table.fill_material_table` 按 `compute_layout(bom)` **变行重构**(据每料成份数动态算行+动态合并：A/B/C 零件级、D 类别组、E/F 材质、K..AD 报告块)。
- **段二 COM 嵌 OLE**：`hitl/ole_assemble.py:embed_many`(WPS `KET.Application` / Excel)。**OLE 经 COM 嵌入后该 xlsx 不可再用 openpyxl 保存(会丢 OLE)**→ OLE 必须最后一次性嵌，照片(openpyxl)在 COM 之前。
- **放置引擎** `hitl/placement_plan.py`：stage2 文件↔材质链 → embed specs（材质表 K/L/Y 结构驱动 `mat_anchors_nocrutch`；材质证明 part 分组横排；部件/UL/信赖性 GRID；图纸/包装/出货 固定位）。
- **总装** `hitl/assemble_order.py:assemble_job`(读 state → 段一 → 段二，子进程跑 COM)。

---

## 4. 关键文件地图

| 层 | 文件 |
|---|---|
| B 抽取 | `hitl/material_extract.py`(to_proposal/propose_bom_from_pile/enrich_rohs/candidate_msds) · `spike/extract.py`(curl 调 qwen) · `spike/assemble.py` |
| 字典 | `hitl/dicts.py` + `hitl/data/*.json`(见§5) · `hitl/file_match.py`(ALIAS 种子) |
| BOM/材质表 | `hitl/material_table.py`(compute_layout/inject_data/assemble_row/normalize_*) |
| 文件↔材质链 | `hitl/file_link.py`(link_materials) · `hitl/file_router.py`(route 分类) |
| OLE 放置/装配 | `hitl/placement_plan.py` · `hitl/ole_placement.py`(ev_col/part_top) · `hitl/ole_assemble.py`(embed_many/com_session/verify_open) · `study/embed_structure.py`(GRID/count_from_bom) |
| 图纸/FAI/照片 | `hitl/drawing_extract.py`(qwen-vl) · `hitl/fai.py`(spec_limits) · `hitl/sample_photo.py` |
| 校验 | `app/rules.py`(validate_confirm/validate_bom/validate_filetree/export_preflight) · `hitl/validate.py`(齐套/有效期/未填/溯源) |
| golden/对标 | `study/golden_parse.py`(parse_golden) · `study/case_data.py`(to_inject_bom) · `study/build_pseudo_order.py`(伪真单) |
| 前端纯逻辑(可 node 单测) | `app/web/js/{bomstate,treestate,resolve,recompute,exportstate}.js` |
| 无拐杖 e2e | `run_m21.py`(走骨架) `run_m23_e2e.py`(BOM) `run_m24_e2e.py`(放置) `run_m25_e2e.py`(导出) |

---

## 5. 五本全局字典 + 材质为锚模型

**字典**(`hitl/data/*.json`，**从全 39 份 golden 承认书聚合校准**，全局跨客户、持久化、UI 改即 learn 回写)：
1. `材质简称字典.json` {标准名:[token变体]} — B 原文→标准名(FRIANYL→PA66、POFEX→XLPE)。规范化包含匹配、最长 token 胜。
2. `材质类别零件字典.json` {标准材质名:{材质类别,零件}} — 反查派生(PA66→胶座/胶座端子)。冲突取多数(PVC 默认线材/导线，例外 PVC套管人工覆盖)。
3. `供应商历史.json` [16家] — 零件级下拉。
4. `零件顺序.json` — 拖动排序，材质表项次跟随。
5. `成份名称词表.json` {材质:{cas:标准短名}} — G 列成份名标准化(錫(Sn)→SN、Titanium dioxide→钛白粉)，inject_data 用。

**材质为锚**(核心 UX)：B(`to_proposal`)只产 **材质原文+成分**(去供应商)；BOM 页操作员改材质名 → `dicts.resolve_material`(前端 `resolve.js` 镜像，node-parity) → 标准名 + **反查类别/零件自动派生**；未知→人工设→回写学习。供应商**零件级手填**；成分可增删改、**无CAS 标黄**交人工删；零件组⠿拖动排序。

---

## 6. 工程纪律

1. **TDD 金字塔**：纯函数 pytest + **无拐杖伪真单 e2e**(从 golden 反构原始输入、藏真值、对标 golden) + **UI 必须视觉截图验证**(Edge `--headless` 渲 PNG，光看代码/计数不算——OLE 页/材质证明页曾因此翻车)。
2. **node-parity**：任何前端 JS 算法跑 node 必须 == 后端 Python(防口径漂移)。见 `tests/test_*_parity.py`。
3. **每里程碑 commit + push GitHub**(off-machine 保险——本项目曾被云同步回滚吞代码+损坏 git；已暂停同步)。commit 格式 `type(scope): subject` + `Co-Authored-By: Claude...`。
4. **双闸验收**：机器自检(测试+渲染)绿 → 交老板手测 → 确认/打回。
5. **安全红线**(见公司 CLAUDE.md §10)：LLM **只走官方第一方 DashScope/通义端点**(不进训练、不经第三方聚合中转站)；**qwen 不可用 → 停下问老板，绝不换第三方**。客户数据(.work/本单输入)不入库。
6. **开发期 no-cache**：`server.py` 中间件让前端静态不缓存(否则改了 JS 浏览器跑旧版，手测看不到变化)。

---

## 7. 关键不变式与陷阱（踩过的坑）

- **🔴 同源同序**(最高不变式)：段一填格 `fill_material_table` 与段二放置 `mat_anchors_nocrutch` 必须吃**同一个 `stage2_to_nested_bom` 的 nested_bom 实例**；`ordered` 序 == `compute_layout` 展开序 → 否则材质表 OLE **落错行**。
- **材质类别是零件下子分组**(别理解成自由选)：一零件可多类别(胶座端子→胶座+端子)；油墨属线材、不是独立类别；**不坍缩**(早期 to_inject_bom 把多类别零件坍成只首类别)。
- **聚合物多 CAS 号**：PA66 源 37640-57-6 vs golden 63428-84-2(都尼龙66)→CAS 对不上，反查/对标靠**材质名兜底**。
- **LLM**：文本抽取 `qwen3.7-plus`(`enable_thinking:false`，旧 `qwen-plus` 撞 FreeTierOnly 403)；图纸 FAI `qwen-vl-max`；curl 必带 `--noproxy * --ssl-no-revoke`(Clash 代理劫持国内 API + schannel 吊销坑)。缓存键含 provider|model。
- **WPS COM**：慢/可能僵尸进程(`com_session` 四必设+退出强杀；总装走子进程+超时)；WPS `OLEObjects().Add` 忽略位置参数→Add 后显式设 .Left/.Top。
- **本机怪癖**：`import` 某些库(sqlalchemy 等)随机挂死(WMI/platform，sitecustomize 修)；pdfplumber/pdftotext 随机挂(`_safe` 守护线程超时)；GBK 控制台对 ✓✗/中文易乱码(用 utf-8 wrapper)。
- **golden `YY60039397` 损坏**(嵌错 402 图)——别当真值，已污染 e2e，对标须 SKIP。
- demo job(demo403/demoxlpe/demopvc) 是 `.work` 临时单，可能残缺(无 drawing/stage1)；干净原始输入在 `本单输入/手测-<code>/`。

---

## 8. 测试与运行

```bash
python -m pytest tests/ -q                              # 110+ 测全绿(纯函数+node-parity)
python -m uvicorn app.server:app --host 127.0.0.1 --port 8733   # 起本地 Web
python run_m24_e2e.py            # 无拐杖 spec 级 e2e；--com <案> 真 COM 装配
python run_m25_e2e.py demo403   # 导出 e2e(注照片→装配→verify_open)
```
手测：`http://127.0.0.1:8733/index.html?job=demo403`(走①→⑤)。原始输入 `本单输入/手测-{YY60039403,YY60010118,YY60030529}/`。DASHSCOPE_API_KEY 在 User 环境变量。

---

## 9. 进度与待办

**已完成**(push GitHub)：M1 装配引擎 → M2.1 无拐杖走骨架 → M2.2 确认环① → M2.3 BOM脊柱+接真B → M2.4 确认环②文件树+段二装配 → M2.5 照片+导出 → **B段重构(材质为锚)+5字典校准** → **手测反馈批次**：全局qwen3.7-plus(图纸也切, 实证更优)、④文件树继承③零件顺序/豁免、建议归属(认不准报告按色/token建议挂)、FAI豁免尺寸跳过、**重量%多除100根治**(范围取中+材质表写float带'0.00%'格式)、核对三态UIUX、**#2 OLE物料标签**(料名/零件名烤进图标, 真COM11嵌验证)。5 步流全线通。
**真输出4缺陷已修(真COM闭环自验)**：①品号取生久料号YY(prompt+_pick_shengjiu_code)+名称去料号留品类导线(_clean_name)；②材质表RoHS空白→enrich三级填充(报告>MSDS自带RoHS声明>ND, PVC声明鎘〈5ppm正用为M-V)；③OLE标题=料名(实测WPS忽略IconLabel→嵌入重命名副本使标题=文件名=标签)+横排按零件序(pile_specs)；④过抽按老板决策不自动滤、无CAS标黄人工删(且声明行数据正用为M-V)。
**UXUI 改版(设计评审4视角+综合→逐页落地, 原生JS栈)**：P0 设计令牌tokens.css+统一步条(删②选型→四步·可点·缺N徽标)+/api/overview+放行门软导航(待办chips常可点滚到待办); P1 ③材质卡两行化+三态拆"状态徽章+独立[标记通过]"+可疑黄条+筛选单选段控+6处原生prompt→页内面板(豁免预设留痕)+④空槽软硬显形(MSDS橙必补/第三方灰可空); 断点续做首页(/api/orders+本单列表进度+续做); P2 拖拽落点持续高亮+自动保存可见; 收尾 撤销(删成分/移下文件)+⑤溯源缺值标红/去④改回改链+P3品牌头(SJ logo/favicon); ①核对统一③(状态徽章+独立标记通过)+①③一键核对所有; ③同零件材质拖序(传装表); **成长型建议归属**(归属学习.json在线学④确认真值→泛化→suggest_for/_infer_part据='学')。共享件: steps.js/gate.js/dialog.js/tokens.css。预览: launch.json drawing-gate(8731)。
**待办**：FAI 未用行 #DIV/0 清理、部件承认书横排零件序仅部分(型号码文件名如1061/A2501推不出零件)、PA66 漏抽、PVC套管歧义、真单端到端手测、**PyInstaller 打包发布**(看板 T-2026-007)。
**10单闭环测试(run_demo10_e2e.py + eyetest_demo10.py)**：自主管线对标golden逐格。覆盖96%/材质名98%/类别96%/零件96%/成份名96%/CAS88%/RoHS90%/重量单值72%/重量区间0%。**CAS与重量缺口经逐一核实=源完整性(MSDS整缺/只含添加剂不含基材)+golden人工录入(文本范围如10-30%、与嵌入MSDS不同值), 非抽取bug**(源里有的部分~97%)。基材缺(PA66的NYLON66)按老板定: 操作员③手动'+增成分行'补, 不自动造数据。
**关键诊断(踩过)**：①重量"多除100"非LLM抽取错, 是 normalize 取范围低端+'-'当负号 & 写字符串进'0.00%'单元格裸显; 修=范围取中+float+格式。②图纸 qwen3.7-plus > qwen-vl-max(品号 YY 不误读YV)。③**OLE标题=嵌入文件名**(WPS忽略IconLabel/自定义图标, PDF导出显通用图标)→改标签即嵌入重命名副本。④材质表M-V/重量列为'0.00%'/小数占比, 写float才渲百分数。⑤_clean_name勿用\w(吞中文品类), 用ASCII。

## 10. 起手式
1. 读 memory：`MEMORY.md` 索引 + `jiuyi-*.md`(项目史/架构/抽取/字典/坑)，比代码注释更全。
2. git remote 私有：`D-Tony2020/JIUYI-Automation-of-Approval-Documents`。
3. 看板卡 `.harness/board/` 的 `T-2026-*-久益-*`。
4. 改前端→老板手测前提醒 Ctrl+Shift+R(虽有 no-cache)；改 OLE/材质表→必须真 COM 渲染眼检。
