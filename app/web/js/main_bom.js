// 确认环③ BOM脊柱编辑器(材质为锚)。改材质名→简称字典出标准名→反查类别/零件自动填(可覆盖);
// 成份可增删改+无CAS标黄; 供应商零件组级(历史下拉+新建); 保存时回写字典记忆。
import * as api from "./api.js";
import { groupByPart, detectDups, suspect, allMissing, materialMissing, cardState } from "./bomstate.js";
import { resolveMaterial } from "./resolve.js";

const S = { job: null, materials: [], dicts: { alias: {}, catpart: {}, suppliers: [] },
            view: { group: true, filter: null, q: "" }, expanded: new Set() };
const $ = (id) => document.getElementById(id);
let saveTimer = null;

async function boot() {
  const job = new URLSearchParams(location.search).get("job");
  $("file").addEventListener("change", onUpload);
  try { S.dicts = await api.getDict(); } catch { /* 用默认空字典 */ }
  if (job) {
    S.job = job;
    try {
      const s = await api.getBomState(job); S.materials = s.materials || [];
      autoResolveAll();
      const exp = new URLSearchParams(location.search).get("exp"); if (exp) S.expanded.add(+exp);
      afterExtract();
    } catch { /* 未提议, 等上传 */ }
  }
}

async function onUpload(e) {
  const files = [...e.target.files];
  if (!files.length) return;
  if (!S.job) S.job = "job_" + Math.random().toString(36).slice(2, 10);
  setBusy(`上传 ${files.length} 份材料…`);
  await api.uploadMaterials(S.job, files);
  setBusy(`qwen 读 MSDS 中(每份约 10–20 秒)…`);
  const r = await api.bomExtract(S.job);
  S.materials = r.materials || [];
  autoResolveAll();
  afterExtract();
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
  return `<div class="card mat-card ${m.手补 ? "manual" : ""}" data-st="${st}" data-i="${i}">
    ${m.手补 ? '<div class="manual-tag">手动补 · 无MSDS</div>' : ""}
    ${dupOf[i] !== undefined ? '<div class="dup-tag">⚠ 同名材质重复?<button data-merge="' + dupOf[i] + '">合并</button> <button data-keepdup="' + dupOf[i] + '">都保留</button></div>' : ""}
    <div class="mat-row">
      <span class="matdraghandle" draggable="true" data-matdrag="${i}" title="拖到别的零件组即改归属(传递到装表)">⠿</span>
      ${verifyBtn(i, m, open)}
      <input type="checkbox" data-sel="${i}">
      <input class="inp matname-in" data-mat="${i}" value="${esc(m.材质)}" title="原文:${esc(m.材质原文) || "—"} · 改为标准名→自动出类别/零件" placeholder="材质(标准名)">
      <select class="inp part-sel ${m.零件 ? "" : "need"}" data-part="${i}">${partOpts}</select>
      <select class="inp ${m.材质类别 ? "" : "need"}" data-cat="${i}">${catOpts}</select>
      <span class="pill">成分${(m.成份 || []).length}${noCas ? `·⚠无CAS${noCas}` : ""}${reasons.length ? "·⚠" + reasons.length : ""}</span>
      <button class="exbtn" data-exempt="${i}">${m.豁免 ? "取消豁免" : "豁免"}</button>
    </div>
    ${open ? block(i, reasons) : ""}
  </div>`;
}

function verifyBtn(i, m, open) {
  // 核对三态机(左侧): 未核对→[核对](一击展开成分) ; 展开未通过→[核对通过✓](再击通过) ; 已核对→[✓已通过](击=取消改)
  if (m.豁免) return `<button class="verifybtn" data-vs="exempt" disabled>豁免</button>`;
  const vs = m.已核对 ? "passed" : (open ? "ready" : "idle");
  const label = { idle: "核对 ▾", ready: "核对通过 ✓", passed: "✓ 已通过" }[vs];
  const title = { idle: "点击展开成分核对", ready: "再点一次=核对通过", passed: "已通过 · 点击取消并修改" }[vs];
  return `<button class="verifybtn" data-verify="${i}" data-vs="${vs}" title="${title}">${label}</button>`;
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
  $("toolbar").innerHTML = `
    <button id="addmanual">+ 手动补材质</button>
    <select id="batchpart"><option value="">批量设零件▾</option>${parts().map((p) => `<option>${esc(p)}</option>`).join("")}<option value="__new__">➕新建…</option></select>
    <label><input type="checkbox" id="grouptoggle" ${S.view.group ? "checked" : ""}> 按零件分组</label>
    <label><input type="checkbox" id="ftodo" ${S.view.filter === "todo" ? "checked" : ""}> 只看待补</label>
    <label><input type="checkbox" id="fwarn" ${S.view.filter === "warn" ? "checked" : ""}> 只看标黄</label>
    <input id="search" placeholder="搜索 材质/原文/源文件" value="${esc(S.view.q)}">`;
  $("addmanual").onclick = addManual;
  $("batchpart").onchange = (e) => batchAssign(e.target.value);
  $("grouptoggle").onchange = (e) => { S.view.group = e.target.checked; render(); };
  $("ftodo").onchange = (e) => { S.view.filter = e.target.checked ? "todo" : null; render(); };
  $("fwarn").onchange = (e) => { S.view.filter = e.target.checked ? "warn" : null; render(); };
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
    el.addEventListener("dragstart", (e) => { e.stopPropagation(); S.matDrag = +el.dataset.matdrag; S.pgDrag = null; e.dataTransfer.effectAllowed = "move"; });
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
  document.querySelectorAll("[data-verify]").forEach((el) => el.onclick = () => onVerify(+el.dataset.verify));
  document.querySelectorAll("[data-exempt]").forEach((el) => el.onclick = () => toggleExempt(+el.dataset.exempt));
  document.querySelectorAll("[data-merge]").forEach((el) => el.onclick = () => mergeDup(+el.dataset.merge));
  document.querySelectorAll("[data-keepdup]").forEach((el) => el.onclick = () => {});
  document.querySelectorAll(".cmp").forEach((el) => el.onchange = () => editComp(el.dataset.c, el.value));
  document.querySelectorAll("[data-delc]").forEach((el) => el.onclick = () => delComp(el.dataset.delc));
  document.querySelectorAll("[data-addc]").forEach((el) => el.onclick = () => addComp(+el.dataset.addc));
  $("gatebtn").onclick = onConfirm;
}

function onVerify(i) {                        // 核对三态机: 未核对→展开成分; 展开未通过→通过(收起); 已通过→取消并展开改
  const m = S.materials[i];
  if (m.豁免) return;
  if (m.已核对) { m.已核对 = false; S.expanded.add(i); }                  // 取消通过→展开可改
  else if (S.expanded.has(i)) { m.已核对 = true; S.expanded.delete(i); }   // 一击展开后再击=通过→收起清爽
  else { S.expanded.add(i); }                                            // 首击=展开成分供核对
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

function setPart(i, val) {
  if (val === "__new__") { const p = prompt("新建零件名（导线/胶座端子/热缩管/锡…）:"); if (!p) { render(); return; } S.materials[i].零件 = p.trim(); }
  else S.materials[i].零件 = val;
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
  S.materials[i].成份.splice(j, 1); save(); render();
}

function addComp(i) {
  (S.materials[i].成份 = S.materials[i].成份 || []).push({ 成份名称: "", CAS: "", "重量%": "", 无CAS: true });
  save(); render();
}

function batchAssign(val) {
  const sel = [...document.querySelectorAll("[data-sel]:checked")].map((el) => +el.dataset.sel);
  if (!sel.length) { alert("先勾选要批量归组的材质"); render(); return; }
  let p = val;
  if (val === "__new__") { p = prompt("新建零件名:"); if (!p) { render(); return; } p = p.trim(); }
  if (!p) { render(); return; }
  sel.forEach((i) => S.materials[i].零件 = p);
  save(); render();
}

function addManual() {
  S.materials.push({ 材质: "", 材质原文: "", 成份: [], RoHS: {}, 零件: "", 材质类别: "", 已核对: false, 手补: true });
  render();
}

function toggleExempt(i) {
  const m = S.materials[i];
  if (m.豁免) { delete m.豁免; delete m.豁免原因; }
  else { const r = prompt("豁免原因（本料无MSDS已附REACH / 源缺）:", "本料无MSDS"); if (!r) { render(); return; } m.豁免 = true; m.豁免原因 = r; m.已核对 = false; }
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
  $("summary").textContent = miss.length ? "还差: " + miss.slice(0, 8).join(" · ") + (miss.length > 8 ? ` …共${miss.length}` : "")
    : `BOM脊柱已齐（${S.materials.length}条${exN ? `·豁免${exN}` : ""}）`;
  $("gatebtn").disabled = miss.length > 0;
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
  saveTimer = setTimeout(() => api.bomSave(S.job, { materials: S.materials }).catch(() => {}), 800);
}

async function onConfirm() {
  setBusy("提交…");
  try {
    await api.learnDict(dictLearnPayload()).catch(() => {});      // 回写字典记忆
    S.dicts = await api.getDict().catch(() => S.dicts);
    await api.bomConfirm(S.job, { materials: S.materials });
    const next = "index_filetree.html?job=" + encodeURIComponent(S.job);
    $("summary").innerHTML = `✅ BOM脊柱已确认 · <a href="${next}">进入 ④文件树 →</a>`; $("gatebtn").disabled = true;
    setTimeout(() => { location.href = next; }, 900);
  } catch (e) { setBusy(""); alert("放行被拦：" + e.message); }
}

function setBusy(t) { $("busy").textContent = t; $("busy").style.display = t ? "block" : "none"; }
function esc(s) { return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

boot();
