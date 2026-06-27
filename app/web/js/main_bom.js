// 确认环③ BOM脊柱编辑器(材质为锚)。改材质名→简称字典出标准名→反查类别/零件自动填(可覆盖);
// 成份可增删改+无CAS标黄; 供应商零件组级(历史下拉+新建); 保存时回写字典记忆。
import * as api from "./api.js";
import { groupByPart, detectDups, suspect, allMissing, materialMissing, cardState } from "./bomstate.js";
import { renderGate, scrollFirstTodo } from "./gate.js";
import { dlgPrompt, toast, savedTick, EXEMPT_REASONS } from "./dialog.js";
import { resolveMaterial } from "./resolve.js";

const S = { job: null, materials: [], dicts: { alias: {}, catpart: {}, suppliers: [] },
            view: { group: true, filter: null, q: "" }, expanded: new Set() };
const $ = (id) => document.getElementById(id);
let saveTimer = null;

async function boot() {
  const job = new URLSearchParams(location.search).get("job");
  $("file").addEventListener("change", onUpload);
  $("openpool").onclick = onOpenPool;                              // 材料文件池: 打开文件夹直拖
  window.addEventListener("focus", () => { if ($("uploadbar").style.display !== "none" && S.job) renderPool(); });  // 从资源管理器切回→刷新池
  try { S.dicts = await api.getDict(); } catch { /* 用默认空字典 */ }
  if (job) {
    S.job = job;
    let got = null;
    try { got = await api.getBomState(job); } catch { /* 未提议(404), 停上传页 */ }
    S.materials = (got && got.materials) || [];
    if (S.materials.length) {
      autoResolveAll();
      const exp = new URLSearchParams(location.search).get("exp"); if (exp) S.expanded.add(+exp);
      afterExtract();
    } else {
      renderPool();                                                // 未提议→停上传页+显材料池(已直拖的可见)
    }
  }
}

function ensureJob() {
  if (!S.job) {
    S.job = "job_" + Math.random().toString(36).slice(2, 10);
    const u = new URL(location.href); u.searchParams.set("job", S.job); history.replaceState(null, "", u);  // 写回URL→刷新可续做
  }
}

async function onUpload(e) {
  const files = [...e.target.files];
  if (!files.length) return;
  ensureJob();
  setBusy(`上传 ${files.length} 份材料…`);
  await api.uploadMaterials(S.job, files);
  setBusy(`qwen 读 MSDS 中(每份约 10–20 秒)…`);
  const r = await api.bomExtract(S.job);
  S.materials = r.materials || [];
  if (!S.materials.length) {                                      // 0材质别跳空工作区, 停上传页+解释(同 onReadPool)
    setBusy("");
    toast("没读到可用的 MSDS 材质。注意：RoHS/REACH 等是报告不算材质源；若某 PDF 读不出文字也会漏(见下方文件池类型标注)。", "err");
    renderPool(); return;
  }
  autoResolveAll();
  afterExtract();
}

// 材料文件池: 打开文件夹(创建/沿用本单), 供把散落各处的 MSDS/报告直接拖进来
function onOpenPool() {
  ensureJob();
  api.openMaterials(S.job).then((r) => {
    toast(r.ok ? "已打开材料文件池，把散落的 MSDS/报告拖进 materials\\ 后回来点「读取并抽取」" : "打开失败：" + (r.err || ""), r.ok ? "ok" : "err");
    renderPool();
  });
}

// 读取材料池并抽取(拖入=上传; 文件已在 materials/, 直接 bomExtract)
async function onReadPool() {
  if (!S.job) { toast("先点「打开材料文件池」放入文件", "err"); return; }
  setBusy("qwen 读材料文件池 MSDS（每份约 10–20 秒）…");
  let r; try { r = await api.bomExtract(S.job); } catch (e) { setBusy(""); toast("抽取失败：" + e.message, "err"); return; }
  S.materials = r.materials || [];
  if (!S.materials.length) {
    setBusy("");
    toast("文件池里没读到可用的 MSDS。注意：RoHS/REACH 等是报告不算材质源；若某 PDF 读不出文字也会漏(见下方类型标注)。", "err");
    renderPool(); return;
  }
  autoResolveAll(); afterExtract();
}

async function renderPool() {                                      // 材料文件池实时跟踪(UI上传/直拖都进同一池)
  const el = $("pooltracker"); if (!el) return;
  if (!S.job) { el.innerHTML = ""; return; }
  let r; try { r = await api.pool(S.job); } catch { return; }
  if (!r.count) {
    el.innerHTML = `<div class="pool-head">📥 材料文件池（materials\\）：空 <button class="pool-refresh" id="poolrefresh">刷新</button></div>`
      + `<div class="pool-tip">点上面「📂打开材料文件池」，把散落各处的 MSDS/报告拖进去（拖入=上传）</div>`;
  } else {
    const rows = r.files.map((f) =>
      `<div class="pool-row ${f.已识别 ? "" : "unk"}"><span class="pool-f">${esc(f.文件)}</span><span class="pool-t">${esc(f.类型)}</span></div>`).join("");
    el.innerHTML = `<div class="pool-head">📥 材料文件池（materials\\）· ${r.count} 个文件 `
      + `<button class="pool-refresh" id="poolrefresh">刷新</button>`
      + `<button class="readpool-btn" id="readpool">🔄 读取并抽取材质</button></div>${rows}`;
  }
  const pr = $("poolrefresh"); if (pr) pr.onclick = renderPool;
  const rp = $("readpool"); if (rp) rp.onclick = onReadPool;
}

// 材质为锚: 用 材质原文 反查字典, 自动填 标准名/类别/零件(仅在操作员未填时, 不覆盖)
function autoResolveAll() {
  for (const m of S.materials) {
    const raw = m.材质原文 || m.材质 || "";
    const r = resolveMaterial(raw, S.dicts.alias, S.dicts.catpart);
    if (!m.材质原文) m.材质原文 = raw;
    if (!(m.材质 || "").trim() || m.材质 === raw) m.材质 = r.标准名;
    if (!(m.材质类别 || "").trim()) m.材质类别 = r.材质类别;
    if (!(m.零件 || "").trim()) m.零件 = r.零件;
  }
}

function afterExtract() {
  setBusy("");
  $("uploadbar").style.display = "none";
  $("workspace").style.display = "block";
  render();
}

// ── 渲染 ────────────────────────────────────────────────────
function parts() { return [...new Set(S.materials.map((m) => (m.零件 || "").trim()).filter(Boolean))]; }

function orderParts(order) {   // 按持久化零件顺序排(序内在前, 序外保原序)
  const po = S.dicts.part_order || [];
  const idx = {}; po.forEach((p, i) => (idx[p] = i));
  return [...order].sort((a, b) => (idx[a] == null ? po.length : idx[a]) - (idx[b] == null ? po.length : idx[b]));
}

function reorderParts(from, to) {   // 拖动改零件顺序 + 持久化(保留他单零件)
  if (!from || !to || from === to) return;
  const cur = orderParts(parts());
  const fi = cur.indexOf(from), ti = cur.indexOf(to);
  if (fi < 0 || ti < 0) return;
  cur.splice(fi, 1); cur.splice(ti, 0, from);
  const merged = cur.concat((S.dicts.part_order || []).filter((p) => !cur.includes(p)));
  S.dicts.part_order = merged;
  api.learnDict({ part_order: merged }).catch(() => {});
  render();
}

function render() {
  renderToolbar();
  const { parts: grp, order, unclaimed } = groupByPart(S.materials);
  const dups = detectDups(S.materials);
  const dupOf = {}; dups.forEach((g, k) => g.forEach((i) => (dupOf[i] = k)));
  let html = "";
  if (unclaimed.length) {
    html += `<div class="unclaimed" data-partdrop=""><div class="part-head warn">⚠ 待认领零件 ${unclaimed.length} 件（改材质名自动归零件；改不出则手选；拖材质到此=移出零件）</div>`
      + unclaimed.filter(passFilter).map((i) => card(i, dupOf)).join("") + `</div>`;
  }
  if (S.view.group) {
    for (const p of orderParts(order)) {
      const idxs = grp[p].filter(passFilter);
      const sup = supplierOf(p);
      html += `<div class="part-group" data-partdrop="${esc(p)}"><div class="part-head" draggable="true" data-pgdrag="${esc(p)}" title="拖动调零件顺序(持久化)">`
        + `<span class="draghandle">⠿</span> ▸ ${esc(p)} <small>${grp[p].length}件</small>`
        + ` · 供应商 <input class="inp psup" list="suplist" data-psup="${esc(p)}" value="${esc(sup)}" placeholder="零件级手填">`
        + `</div>` + idxs.map((i) => card(i, dupOf)).join("") + `</div>`;
    }
  } else {
    html += S.materials.map((m, i) => i).filter((i) => S.materials[i].零件 && passFilter(i)).map((i) => card(i, dupOf)).join("");
  }
  const datalist = `<datalist id="suplist">${(S.dicts.suppliers || []).map((s) => `<option value="${esc(s)}">`).join("")}</datalist>`;
  $("bomtable").innerHTML = datalist + (html || "<p class='tip'>无匹配材质</p>");
  bind();
  refresh();
}

function supplierOf(p) {   // 零件级供应商(取该零件首个材质的, 反范式化共享)
  const m = S.materials.find((x) => (x.零件 || "").trim() === p && (x.供应商 || "").trim());
  return m ? m.供应商 : "";
}

function passFilter(i) {
  const m = S.materials[i];
  if (S.view.filter === "todo" && materialMissing(m, i).length === 0) return false;
  if (S.view.filter === "warn" && suspect(m).length === 0) return false;
  if (S.view.q) {
    const q = S.view.q.toLowerCase();
    if (![m.材质, m.材质原文, m.源文件].some((x) => String(x || "").toLowerCase().includes(q))) return false;
  }
  return true;
}

const CATS = ["线材", "胶座", "端子", "套管", "锡丝", "镀层", "其他"];

function card(i, dupOf) {
  const m = S.materials[i], st = cardState(m, i), reasons = suspect(m), open = S.expanded.has(i);
  const noCas = (m.成份 || []).filter((c) => c.无CAS).length;
  const partOpts = ['<option value="">← 选零件</option>']
    .concat(parts().map((p) => `<option ${m.零件 === p ? "selected" : ""}>${esc(p)}</option>`))
    .concat('<option value="__new__">➕ 新建零件…</option>').join("");
  const catOpts = ['<option value="">类别</option>']
    .concat(CATS.map((c) => `<option ${m.材质类别 === c ? "selected" : ""}>${c}</option>`)).join("");
  const passed = !!m.已核对, ex = !!m.豁免;
  const badge = ex ? `<span class="mbadge ex">豁免</span>`
    : passed ? `<span class="mbadge pass">✓ 已通过</span>`
      : open ? `<span class="mbadge ready">可核对</span>`
        : `<span class="mbadge todo">待核对</span>`;
  return `<div class="card mat-card ${m.手补 ? "manual" : ""}" data-st="${st}" data-i="${i}">
    ${m.手补 ? '<div class="manual-tag">手动补 · 无MSDS</div>' : ""}
    ${dupOf[i] !== undefined ? '<div class="dup-tag">⚠ 同名材质重复?<button data-merge="' + dupOf[i] + '">合并</button> <button data-keepdup="' + dupOf[i] + '">都保留</button></div>' : ""}
    <div class="mat-row1">
      ${badge}
      <input class="inp matname-in" data-mat="${i}" value="${esc(m.材质)}" title="原文:${esc(m.材质原文) || "—"} · 改为标准名→自动出类别/零件" placeholder="材质(标准名)">
      <select class="inp part-sel ${m.零件 ? "" : "need"}" data-part="${i}">${partOpts}</select>
      <select class="inp ${m.材质类别 ? "" : "need"}" data-cat="${i}">${catOpts}</select>
      <button class="cmp-toggle" data-exp="${i}">成分${(m.成份 || []).length} ${open ? "▾" : "▸"}</button>
    </div>
    <div class="mat-row2">
      <span class="matdraghandle" draggable="true" data-matdrag="${i}" title="拖到别的零件组即改归属(传递到装表)">⠿ 拖</span>
      <label class="bulk-sel" title="勾选后用工具行'批量设零件'"><input type="checkbox" data-sel="${i}"> 批量选</label>
      ${noCas ? `<span class="nocas-tip">⚠ 无CAS ${noCas}</span>` : ""}
      <span class="row2-right">
        ${ex ? `<button class="exbtn" data-exempt="${i}">取消豁免</button>`
      : `<button class="passbtn ${passed ? "on" : ""}" data-pass="${i}">${passed ? "取消通过" : "标记通过"}</button> <button class="exbtn" data-exempt="${i}">豁免</button>`}
      </span>
    </div>
    ${reasons.length ? `<div class="susp-bar" data-exp="${i}">⚠ ${esc(reasons.join(" · "))} ▾ 点击展开成分定位</div>` : ""}
    ${open ? block(i, reasons) : ""}
  </div>`;
}

function block(i, reasons) {
  const m = S.materials[i];
  const rows = (m.成份 || []).map((c, j) =>
    `<tr class="${c.无CAS ? "nocas" : ""}">
      <td><input class="cmp" data-c="${i}|${j}|成份名称" value="${esc(c.成份名称)}"></td>
      <td><input class="cmp" data-c="${i}|${j}|CAS" value="${esc(c.CAS)}" placeholder="${c.无CAS ? "无CAS?" : ""}"></td>
      <td><input class="cmp" data-c="${i}|${j}|重量%" value="${esc(wtDisp(c["重量%"]))}" title="输百分数, 如 99 / 0.04 / 余量"></td>
      <td><button class="exbtn" data-delc="${i}|${j}">✕</button></td></tr>`).join("");
  const ro = Object.entries(m.RoHS || {}).map(([k, v]) => {
    const bad = v && !["ND", "NA", ""].includes(String(v).toUpperCase());
    return `<span class="rohs-pill ${bad ? "bad" : "ok"}">${k}:${esc(v) || "—"}</span>`;
  }).join("");
  return `<div class="block ${reasons.length ? "warn" : ""}">
    <div class="block-head">报告 ${esc(m.报告编号) || "(无报告号)"} · ${esc(m.报告日期) || "—"} · 源:${esc(m.源文件) || "—"} · 无CAS行标黄请核/删</div>
    <table class="comp"><tr><th>成份</th><th>CAS</th><th>重量%</th><th></th></tr>${rows}</table>
    <button class="exbtn" data-addc="${i}">+ 增成分行</button>
    <div class="rohs">${ro}</div>
  </div>`;
}

// ── 工具行 ──────────────────────────────────────────────────
function renderToolbar() {
  const f = S.view.filter || "all";
  const seg = (v, t) => `<button class="seg-btn ${f === (v || "all") ? "on" : ""}" data-filter="${v}">${t}</button>`;
  $("toolbar").innerHTML = `
    <span class="tb-grp"><b class="tb-lbl">增/批量</b>
      <button id="addmanual">+ 手动补材质</button>
      <select id="batchpart"><option value="">批量设零件▾</option>${parts().map((p) => `<option>${esc(p)}</option>`).join("")}<option value="__new__">➕新建…</option></select>
      <button id="passallbom" class="passall-btn">✓ 一键核对所有</button></span>
    <span class="tb-grp"><b class="tb-lbl">视图</b>
      <label><input type="checkbox" id="grouptoggle" ${S.view.group ? "checked" : ""}> 按零件分组</label>
      <span class="seg">${seg("", "全部")}${seg("todo", "待补")}${seg("warn", "标黄")}</span></span>
    <input id="search" placeholder="搜索 材质/原文/源文件" value="${esc(S.view.q)}">`;
  $("addmanual").onclick = addManual;
  $("passallbom").onclick = () => { S.materials.forEach((m) => { if (!m.豁免) m.已核对 = true; }); save(); render(); };  // 一键核对所有(非豁免)
  $("batchpart").onchange = (e) => batchAssign(e.target.value);
  $("grouptoggle").onchange = (e) => { S.view.group = e.target.checked; render(); };
  document.querySelectorAll("[data-filter]").forEach((el) => el.onclick = () => { S.view.filter = el.dataset.filter || null; render(); });
  $("search").oninput = (e) => { S.view.q = e.target.value; render(); };
}

// ── 事件 ────────────────────────────────────────────────────
function bind() {
  document.querySelectorAll("[data-mat]").forEach((el) => el.onchange = () => setMat(+el.dataset.mat, el.value));
  document.querySelectorAll("[data-part]").forEach((el) => el.onchange = () => setPart(+el.dataset.part, el.value));
  document.querySelectorAll("[data-cat]").forEach((el) => el.onchange = () => { S.materials[+el.dataset.cat].材质类别 = el.value; save(); render(); });
  document.querySelectorAll("[data-psup]").forEach((el) => el.onchange = () => setPartSupplier(el.dataset.psup, el.value));
  document.querySelectorAll(".part-head[draggable]").forEach((el) => {
    el.addEventListener("dragstart", (e) => { S.pgDrag = el.dataset.pgdrag; S.matDrag = null; e.dataTransfer.effectAllowed = "move"; });
    el.addEventListener("dragover", (e) => { if (S.pgDrag != null) { e.preventDefault(); el.classList.add("pg-over"); } });
    el.addEventListener("dragleave", () => el.classList.remove("pg-over"));
    el.addEventListener("drop", (e) => { if (S.pgDrag == null) return; e.preventDefault(); e.stopPropagation(); el.classList.remove("pg-over"); reorderParts(S.pgDrag, el.dataset.pgdrag); });
  });
  document.querySelectorAll("[data-matdrag]").forEach((el) => {
    el.addEventListener("dragstart", (e) => {
      e.stopPropagation(); S.matDrag = +el.dataset.matdrag; S.pgDrag = null; e.dataTransfer.effectAllowed = "move";
      document.querySelectorAll(".mat-card[data-i]").forEach((c) => { if (+c.dataset.i !== S.matDrag) c.classList.add("drop-active"); });  // 合法落点持续高亮
    });
    el.addEventListener("dragend", () => document.querySelectorAll(".drop-active").forEach((c) => c.classList.remove("drop-active")));
  });
  document.querySelectorAll(".mat-card[data-i]").forEach((el) => {       // 拖材质卡→放到目标卡前: 同零件内排序 / 跨零件移位(均传递到装表)
    el.addEventListener("dragover", (e) => { if (S.matDrag != null && +el.dataset.i !== S.matDrag) { e.preventDefault(); el.classList.add("card-drop-over"); } });
    el.addEventListener("dragleave", () => el.classList.remove("card-drop-over"));
    el.addEventListener("drop", (e) => { if (S.matDrag == null) return; e.preventDefault(); e.stopPropagation(); el.classList.remove("card-drop-over"); reorderMatTo(S.matDrag, +el.dataset.i); S.matDrag = null; });
  });
  document.querySelectorAll("[data-partdrop]").forEach((el) => {           // 材质拖到别的零件组→改归属(传递到装表)
    el.addEventListener("dragover", (e) => { if (S.matDrag != null) { e.preventDefault(); el.classList.add("matdrop-over"); } });
    el.addEventListener("dragleave", () => el.classList.remove("matdrop-over"));
    el.addEventListener("drop", (e) => {
      if (S.matDrag == null) return;
      e.preventDefault(); e.stopPropagation(); el.classList.remove("matdrop-over");
      moveMatToPart(S.matDrag, el.dataset.partdrop); S.matDrag = null;
    });
  });
  document.querySelectorAll("[data-pass]").forEach((el) => el.onclick = () => onPass(+el.dataset.pass));
  document.querySelectorAll("[data-exp]").forEach((el) => el.onclick = () => { const i = +el.dataset.exp; S.expanded.has(i) ? S.expanded.delete(i) : S.expanded.add(i); render(); });
  document.querySelectorAll("[data-exempt]").forEach((el) => el.onclick = () => toggleExempt(+el.dataset.exempt));
  document.querySelectorAll("[data-merge]").forEach((el) => el.onclick = () => mergeDup(+el.dataset.merge));
  document.querySelectorAll("[data-keepdup]").forEach((el) => el.onclick = () => {});
  document.querySelectorAll(".cmp").forEach((el) => el.onchange = () => editComp(el.dataset.c, el.value));
  document.querySelectorAll("[data-delc]").forEach((el) => el.onclick = () => delComp(el.dataset.delc));
  document.querySelectorAll("[data-addc]").forEach((el) => el.onclick = () => addComp(+el.dataset.addc));
  $("gatebtn").onclick = onConfirm;
}

function onPass(i) {                          // [标记通过]/[取消通过] — 独立于展开(展开由成分▸/▾或黄条控制)
  const m = S.materials[i];
  if (m.豁免) return;
  m.已核对 = !m.已核对;
  save(); render();
}

function setMat(i, val) {                    // 改材质名→反查字典自动填类别/零件(操作员未手改过的才覆盖)
  const m = S.materials[i];
  m.材质 = val.trim();
  const r = resolveMaterial(m.材质, S.dicts.alias, S.dicts.catpart);
  if (r.材质类别) m.材质类别 = r.材质类别;     // 字典命中→自动出
  if (r.零件) m.零件 = r.零件;
  save(); render();
}

async function setPart(i, val) {
  if (val === "__new__") {
    const p = await dlgPrompt({ title: "新建零件名", placeholder: "导线 / 胶座端子 / 热缩管 / 锡 …" });
    if (!p) { render(); return; }
    S.materials[i].零件 = p;
  } else S.materials[i].零件 = val;
  save(); render();
}

function reorderMatTo(from, toIdx) {          // 拖材质卡到目标卡前: 同零件内调序(老板要的) / 跨零件移到该位置; 数组序==装表展开序→连续性
  if (from == null || from === toIdx) return;
  const m = S.materials[from], target = S.materials[toIdx];
  m.零件 = (target.零件 || "").trim();        // 落到目标卡所在零件(同零件=纯排序; 异零件=移位并改归属)
  S.materials.splice(from, 1);
  S.materials.splice(S.materials.indexOf(target), 0, m);   // 插到目标卡前
  save(); render();
}

function moveMatToPart(i, p) {                // 拖动改材质归属: 改零件→传递到装表(stage2_to_nested_bom按零件分组+材质表/OLE跟随)
  const m = S.materials[i];
  if (!m) return;
  const tgt = (p || "").trim();
  if ((m.零件 || "").trim() === tgt) return;  // 原地不动
  m.零件 = tgt;                               // 空=移出零件→待认领; 类别(材质级)不变, 由操作员按需调
  save(); render();
}

function setPartSupplier(p, val) {           // 零件级供应商→写该零件所有材质(反范式化)
  S.materials.forEach((m) => { if ((m.零件 || "").trim() === p) m.供应商 = val.trim(); });
  save(); refresh();
}

function wtDisp(v) {                          // 存的是小数占比→按百分数显示(0.99→"99",0.0003→"0.03"); 余量/<x原样
  const s = String(v == null ? "" : v).trim();
  if (!s || s === "余量" || /^[<≤＜>≥＞]/.test(s)) return s;
  const n = parseFloat(s);
  return isNaN(n) ? s : String(+(n * 100).toPrecision(6));
}

function wtParse(s) {                         // 操作员输的百分数→存回小数占比(99→"0.99"); 余量/<x原样
  s = String(s || "").trim();
  if (!s || s === "余量" || /^[<≤＜>≥＞]/.test(s)) return s;
  const n = parseFloat(s.replace("%", ""));
  return isNaN(n) ? s : String(+(n / 100).toPrecision(6));
}

function editComp(token, val) {
  const [i, j, field] = token.split("|");
  const c = S.materials[+i].成份[+j];
  c[field] = (field === "重量%") ? wtParse(val) : val.trim();   // 重量%输的是百分数→存小数占比(与材质表口径一致)
  if (field === "CAS") c.无CAS = !c.CAS || ["/", "-"].includes(c.CAS);
  save(); render();
}

function delComp(token) {
  const [i, j] = token.split("|").map(Number);
  const removed = S.materials[i].成份[j];
  S.materials[i].成份.splice(j, 1); save(); render();
  toast("已删成分", "info", { label: "撤销", fn: () => { S.materials[i].成份.splice(j, 0, removed); save(); render(); } });
}

function addComp(i) {
  (S.materials[i].成份 = S.materials[i].成份 || []).push({ 成份名称: "", CAS: "", "重量%": "", 无CAS: true });
  save(); render();
}

async function batchAssign(val) {
  const sel = [...document.querySelectorAll("[data-sel]:checked")].map((el) => +el.dataset.sel);
  if (!sel.length) { toast("先勾选要批量归组的材质(次行'批量选')", "err"); render(); return; }
  let p = val;
  if (val === "__new__") { p = await dlgPrompt({ title: "新建零件名", placeholder: "零件名" }); if (!p) { render(); return; } }
  if (!p) { render(); return; }
  sel.forEach((i) => (S.materials[i].零件 = p));
  save(); render();
}

function addManual() {
  S.materials.push({ 材质: "", 材质原文: "", 成份: [], RoHS: {}, 零件: "", 材质类别: "", 已核对: false, 手补: true });
  render();
}

async function toggleExempt(i) {
  const m = S.materials[i];
  if (m.豁免) { delete m.豁免; delete m.豁免原因; }
  else {
    const r = await dlgPrompt({ title: "豁免原因(必填, 留痕)", presets: EXEMPT_REASONS });
    if (!r) { render(); return; }
    m.豁免 = true; m.豁免原因 = r; m.已核对 = false;
  }
  save(); render();
}

function mergeDup(k) {
  const g = detectDups(S.materials)[k]; if (!g) return;
  const keep = g[0];
  g.slice(1).forEach((i) => { S.materials[i].豁免 = true; S.materials[i].豁免原因 = "重复(并入" + (S.materials[keep].材质) + ")"; S.materials[i].已核对 = false; });
  save(); render();
}

function refresh() {
  const miss = allMissing(S.materials);
  const exN = S.materials.filter((m) => m.豁免).length;
  S.missing = miss;
  renderGate({
    summaryId: "summary", btnId: "gatebtn",
    missing: miss.map((t) => ({ t, hard: true })),         // ②是硬门
    doneText: `BOM脊柱已齐（${S.materials.length}条${exN ? `·豁免${exN}` : ""}）`,
    nextLabel: "BOM脊柱已齐 → 第3步 挂文件 →",
    rule: "硬门：缺项需先补", todoSel: ".mat-card[data-st='todo'],.mat-card[data-st='warn']",
  });
}

// 收集本单字典学习: 材质原文→标准名(改过的); 标准名→类别/零件; 零件级供应商
function dictLearnPayload() {
  const alias = [], catpart = [], suppliers = [];
  for (const m of S.materials) {
    const std = (m.材质 || "").trim();
    if (m.材质原文 && std && m.材质原文 !== std) alias.push({ 原文: m.材质原文, std });
    if (std && (m.材质类别 || m.零件)) catpart.push({ std, 材质类别: m.材质类别 || "", 零件: m.零件 || "" });
    const sup = (m.供应商 || "").trim();
    if (sup && !suppliers.includes(sup)) suppliers.push(sup);
  }
  return { alias, catpart, suppliers };
}

function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api.bomSave(S.job, { materials: S.materials }).then(savedTick).catch(() => {}), 800);
}

async function onConfirm() {
  if (S.missing && S.missing.length) { scrollFirstTodo(".mat-card[data-st='todo'],.mat-card[data-st='warn']"); return; }
  setBusy("提交…");
  try {
    await api.learnDict(dictLearnPayload()).catch(() => {});      // 回写字典记忆
    S.dicts = await api.getDict().catch(() => S.dicts);
    await api.bomConfirm(S.job, { materials: S.materials });
    const next = "index_filetree.html?job=" + encodeURIComponent(S.job);
    $("summary").innerHTML = `✅ BOM脊柱已确认 · <a href="${next}">进入 ④文件树 →</a>`; $("gatebtn").disabled = true;
    setTimeout(() => { location.href = next; }, 900);
  } catch (e) { setBusy(""); toast("放行被拦：" + e.message, "err"); }
}

function setBusy(t) { $("busy").textContent = t; $("busy").style.display = t ? "block" : "none"; }
function esc(s) { return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

boot();
