// 确认环② 文件树编排(M2.4): 证据文件↔材质↔证据列(K/L/Y) 放置确认 + 拖拽纠正认不准报告 + 豁免。
import * as api from "./api.js";
import { planTree, slotState, filetreeMissing, COLS } from "./treestate.js";
import { renderGate, scrollFirstTodo } from "./gate.js";
import { dlgPrompt, toast, savedTick, EXEMPT_REASONS } from "./dialog.js";

const S = { job: null, bom: { materials: [], unlinked_files: [] }, partOrder: [], gridReports: [], parts: [], drag: null };
const $ = (id) => document.getElementById(id);
let saveTimer = null;

// 证据列 → 拖入时落的 files 桶(放置据此落 K/L/Y; 同 placement_plan.TYPE_COL 反向)
const COL_BUCKET = { K: "其他", L: "REACH", Y: "RoHS" };

async function boot() {
  const job = new URLSearchParams(location.search).get("job");
  if (!job) { $("workspace").innerHTML = "<p class='tip'>缺 job 参数(?job=…)</p>"; return; }
  S.job = job;
  try { S.partOrder = (await api.getDict()).part_order || []; } catch { /* 默认空 */ }   // 继承③零件顺序
  try {
    const s = await api.filetreeState(job);
    S.bom = { materials: s.materials || [], unlinked_files: s.unlinked_files || [], 部件归属: s.部件归属 || {} };
    S.gridReports = s.grid_reports || [];
    S.parts = s.parts || [];
    render();
  } catch (e) {
    $("workspace").innerHTML = `<p class='tip'>读取失败：${esc(e.message)}（请先完成 ③BOM脊柱）</p>`;
  }
}

function render() {
  const tree = planTree(S.bom, S.partOrder);
  let html = "";
  for (const p of tree.order) {
    html += `<div class="part-group"><div class="part-head">▸ ${esc(p)} <small>${tree.parts[p].length}材质</small></div>`;
    for (const mi of tree.parts[p]) html += matRow(tree.materials[mi]);
    html += `</div>`;
  }
  $("bomtable").innerHTML = (html || "<p class='tip'>无材质</p>") + gridReportsHtml();
  renderUnlinked(tree.unlinked);
  $("toolbar").innerHTML = `<span class="tip">绿=已挂证据 · 灰虚=空槽(MSDS必补,第三方可空) · 删除线=豁免</span>`;
  bind();
  refresh();
}

function matRow(m) {
  const real = S.bom.materials[m.idx];
  const cells = COLS.map((col) => {
    const st = slotState(real, col);
    const chips = m.slots[col.key].map((f) =>
      `<span class="filechip" draggable="true" data-from="${m.idx}" data-type="${esc(f.类型)}" data-file="${esc(f.文件)}" title="${esc(f.文件)}">${esc(shortName(f.文件))}<button class="x" data-unlink="${m.idx}|${esc(f.类型)}|${esc(f.文件)}">×</button></span>`).join("");
    const must = col.key === "K";                          // MSDS=唯一硬门必补; L/Y第三方可空
    const empty = m.slots[col.key].length ? ""
      : (real.豁免 ? `<span class="emptyslot opt">—</span>`
        : `<span class="emptyslot ${must ? "must" : "opt"}">${must ? "缺 · 必补" : "可空"}</span>`);
    const sst = (st === "todo" && !must && !real.豁免) ? "opt" : st;   // 第三方空=opt(不算缺)
    return `<div class="slot" data-drop="${m.idx}|${col.key}" data-st="${sst}"><div class="col-label">${col.key} ${col.label}</div>${chips}${empty}</div>`;
  }).join("");
  return `<div class="card mat-card ${m.豁免 ? "exempt" : ""}" data-st="${m.豁免 ? "exempt" : "ok"}" data-i="${m.idx}">
    <div class="mat-row"><span class="matname">${esc(m.材质)}</span>
      <button class="exbtn" data-exempt="${m.idx}">${m.豁免 ? "取消豁免" : "豁免"}</button></div>
    <div class="slot-grid">${cells}</div>
  </div>`;
}

function gridReportsHtml() {
  // 横排部件报告(部件承认/UL/信赖性)归属选择: 选零件→OLE下方部件标签(线材/端子/套管)+顺序。best-effort预填。
  if (!S.gridReports.length) return "";
  const tl = { 部件承认: "部件承认书", UL: "UL证明", 信赖性: "信赖性" };
  const opts = (cur) => ['<option value="">(选零件)</option>']
    .concat(S.parts.map((p) => `<option ${p === cur ? "selected" : ""}>${esc(p)}</option>`)).join("");
  const rows = S.gridReports.map((g) => {
    const cur = (S.bom.部件归属 || {})[g.文件] || g.建议零件 || "";
    return `<div class="grid-row"><span class="gr-tag">${esc(tl[g.表] || g.表)}</span>`
      + `<span class="gr-file" title="${esc(g.文件)}">${esc(shortName(g.文件))}</span><span class="gr-arrow">→</span>`
      + `<select class="gr-sel" data-grpart="${esc(g.文件)}">${opts(cur)}</select></div>`;
  }).join("");
  return `<div class="grid-reports"><div class="gr-head">⊞ 横排部件报告归属 — 选零件定 OLE 下方标签(线材/端子/套管)与顺序；已 best-effort 预填，请核对</div>${rows}</div>`;
}

function renderUnlinked(unlinked) {
  const rows = unlinked.map((u, j) => {
    const s = u.建议;
    const sug = s ? `<button class="sugbtn" data-sug="${j}" title="一点即挂到「${esc(s.材质)}」的 ${esc(s.col)} 列(${s.据 === "色" ? "按颜色" : "按名称"}匹配)">↳建议挂 ${esc(s.材质)}${s.据 === "色" ? " <small>按色</small>" : ""}</button>` : "";
    return `<div class="unl-row"><span class="filechip unl" draggable="true" data-from="unlinked" data-type="${esc(u.类型)}" data-file="${esc(u.文件)}" data-j="${j}" title="${esc(u.文件)}">${esc(shortName(u.文件))} <em>${esc(u.类型)}</em></span>${sug}</div>`;
  }).join("");
  $("unlinked").innerHTML = rows || `<div class="drag-hint">无认不准报告 ✓<br><small>把材质上挂错的也可拖回这里</small></div>`;
}

// ── 拖拽 ────────────────────────────────────────────────────
function bind() {
  document.querySelectorAll(".filechip").forEach((el) => {
    el.addEventListener("dragstart", (e) => {
      S.drag = { from: el.dataset.from, type: el.dataset.type, file: el.dataset.file };
      e.dataTransfer.effectAllowed = "move";
      document.querySelectorAll(".slot, .unlinked-zone").forEach((t) => t.classList.add("drop-active"));  // 拖时所有合法落点持续高亮
    });
    el.addEventListener("dragend", () => document.querySelectorAll(".drop-active").forEach((t) => t.classList.remove("drop-active")));
  });
  document.querySelectorAll(".slot").forEach((el) => {
    el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("drag-over"); });
    el.addEventListener("dragleave", () => el.classList.remove("drag-over"));
    el.addEventListener("drop", (e) => { e.preventDefault(); el.classList.remove("drag-over"); dropTo(el.dataset.drop); });
  });
  const uz = $("unlinked");
  uz.addEventListener("dragover", (e) => { e.preventDefault(); uz.classList.add("drag-over"); });
  uz.addEventListener("dragleave", () => uz.classList.remove("drag-over"));
  uz.addEventListener("drop", (e) => { e.preventDefault(); uz.classList.remove("drag-over"); dropToUnlinked(); });
  document.querySelectorAll("[data-unlink]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); const [i, t, f] = el.dataset.unlink.split("|"); unlinkFile(+i, t, f); });
  document.querySelectorAll("[data-exempt]").forEach((el) => el.onclick = () => toggleExempt(+el.dataset.exempt));
  document.querySelectorAll("[data-sug]").forEach((el) => el.onclick = () => attachSuggested(+el.dataset.sug));
  document.querySelectorAll("[data-grpart]").forEach((el) => el.onchange = () => {   // 横排报告零件归属→标签/顺序
    S.bom.部件归属 = S.bom.部件归属 || {};
    S.bom.部件归属[el.dataset.grpart] = el.value;
    save();
  });
  $("gatebtn").onclick = onConfirm;
}

function _removeFromSource() {
  const d = S.drag;
  if (d.from === "unlinked") {
    S.bom.unlinked_files = S.bom.unlinked_files.filter((u) => !(u.文件 === d.file && u.类型 === d.type));
  } else {
    const fz = S.bom.materials[+d.from].files || {};
    if (Array.isArray(fz[d.type])) fz[d.type] = fz[d.type].filter((x) => x !== d.file);
    else if (fz[d.type] === d.file) fz[d.type] = (d.type === "MSDS") ? "" : [];
  }
}

function dropTo(token) {
  if (!S.drag) return;
  const [miStr, colKey] = token.split("|");
  const mi = +miStr, bucket = COL_BUCKET[colKey];
  _removeFromSource();
  const fz = S.bom.materials[mi].files = S.bom.materials[mi].files || {};
  fz[bucket] = Array.isArray(fz[bucket]) ? fz[bucket] : (fz[bucket] ? [fz[bucket]] : []);
  if (!fz[bucket].includes(S.drag.file)) fz[bucket].push(S.drag.file);
  S.drag = null; save(); render();
}

function attachSuggested(j) {
  const u = S.bom.unlinked_files[j];
  if (!u || !u.建议) return;
  const mi = u.建议.idx, bucket = u.类型 || COL_BUCKET[u.建议.col];   // 落原类型桶(RoHS/SVHC/REACH→对的列)
  S.bom.unlinked_files.splice(j, 1);
  const fz = S.bom.materials[mi].files = S.bom.materials[mi].files || {};
  fz[bucket] = Array.isArray(fz[bucket]) ? fz[bucket] : (fz[bucket] ? [fz[bucket]] : []);
  if (!fz[bucket].includes(u.文件)) fz[bucket].push(u.文件);
  save(); render();
}

function dropToUnlinked() {
  if (!S.drag || S.drag.from === "unlinked") { S.drag = null; return; }
  const d = S.drag; _removeFromSource();
  if (!S.bom.unlinked_files.some((u) => u.文件 === d.file)) S.bom.unlinked_files.push({ 文件: d.file, 类型: d.type });
  S.drag = null; save(); render();
}

function unlinkFile(mi, type, file) {
  const fz = S.bom.materials[mi].files || {};
  if (Array.isArray(fz[type])) fz[type] = fz[type].filter((x) => x !== file);
  else if (fz[type] === file) fz[type] = (type === "MSDS") ? "" : [];
  if (!S.bom.unlinked_files.some((u) => u.文件 === file)) S.bom.unlinked_files.push({ 文件: file, 类型: type });
  save(); render();
}

async function toggleExempt(i) {
  const m = S.bom.materials[i];
  if (m.豁免) { delete m.豁免; delete m.豁免原因; }
  else { const r = await dlgPrompt({ title: "豁免原因(必填, 留痕)", presets: EXEMPT_REASONS }); if (!r) return; m.豁免 = true; m.豁免原因 = r; }
  save(); render();
}

function refresh() {
  const miss = filetreeMissing(S.bom);                     // 缺MSDS=硬门
  const exN = S.bom.materials.filter((m) => m.豁免).length;
  const unl = S.bom.unlinked_files.length;
  S.missing = miss;
  renderGate({
    summaryId: "summary", btnId: "gatebtn",
    missing: miss.map((t) => ({ t, hard: true })),
    doneText: `放置已齐（${S.bom.materials.length}材质${exN ? `·豁免${exN}` : ""}${unl ? `·待拖${unl}` : ""}）`,
    nextLabel: "放置已确认 → 第4步 照片导出 →",
    rule: "缺MSDS不可导出；第三方报告缺将带预警", todoSel: ".mat-card[data-st='todo']",
  });
}

function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api.filetreeSave(S.job, S.bom).then(savedTick).catch(() => {}), 800);
}

async function onConfirm() {
  if (S.missing && S.missing.length) { scrollFirstTodo(".mat-card[data-st='todo']"); return; }
  setBusy("提交…");
  try {
    await api.filetreeConfirm(S.job, S.bom);
    setBusy("");
    const next = "index_export.html?job=" + encodeURIComponent(S.job);
    $("summary").innerHTML = `✅ 文件树已确认 · <a href="${next}">进入 ⑤照片+导出 →</a>`;
    $("gatebtn").disabled = true;
    setTimeout(() => { location.href = next; }, 900);
  } catch (e) { setBusy(""); toast("放行被拦：" + e.message, "err"); }
}

function shortName(s) { s = String(s || ""); return s.length > 22 ? s.slice(0, 20) + "…" : s; }
function setBusy(t) { $("busy").textContent = t; $("busy").style.display = t ? "block" : "none"; }
function esc(s) { return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

boot();
