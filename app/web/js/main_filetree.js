// 确认环② 文件树编排(M2.4): 证据文件↔材质↔证据列(K/L/Y) 放置确认 + 拖拽纠正认不准报告 + 豁免。
import * as api from "./api.js";
import { planTree, slotState, filetreeMissing, COLS } from "./treestate.js";

const S = { job: null, bom: { materials: [], unlinked_files: [] }, drag: null };
const $ = (id) => document.getElementById(id);
let saveTimer = null;

// 证据列 → 拖入时落的 files 桶(放置据此落 K/L/Y; 同 placement_plan.TYPE_COL 反向)
const COL_BUCKET = { K: "其他", L: "REACH", Y: "RoHS" };

async function boot() {
  const job = new URLSearchParams(location.search).get("job");
  if (!job) { $("workspace").innerHTML = "<p class='tip'>缺 job 参数(?job=…)</p>"; return; }
  S.job = job;
  try {
    const s = await api.filetreeState(job);
    S.bom = { materials: s.materials || [], unlinked_files: s.unlinked_files || [] };
    render();
  } catch (e) {
    $("workspace").innerHTML = `<p class='tip'>读取失败：${esc(e.message)}（请先完成 ③BOM脊柱）</p>`;
  }
}

function render() {
  const tree = planTree(S.bom);
  let html = "";
  for (const p of tree.order) {
    html += `<div class="part-group"><div class="part-head">▸ ${esc(p)} <small>${tree.parts[p].length}材质</small></div>`;
    for (const mi of tree.parts[p]) html += matRow(tree.materials[mi]);
    html += `</div>`;
  }
  $("bomtable").innerHTML = html || "<p class='tip'>无材质</p>";
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
    const empty = m.slots[col.key].length ? "" : `<span class="emptyslot">空槽</span>`;
    return `<div class="slot" data-drop="${m.idx}|${col.key}" data-st="${st}"><div class="col-label">${col.key} ${col.label}</div>${chips}${empty}</div>`;
  }).join("");
  return `<div class="card mat-card ${m.豁免 ? "exempt" : ""}" data-st="${m.豁免 ? "exempt" : "ok"}" data-i="${m.idx}">
    <div class="mat-row"><span class="matname">${esc(m.材质)}</span>
      <button class="exbtn" data-exempt="${m.idx}">${m.豁免 ? "取消豁免" : "豁免"}</button></div>
    <div class="slot-grid">${cells}</div>
  </div>`;
}

function renderUnlinked(unlinked) {
  const chips = unlinked.map((u, j) =>
    `<span class="filechip unl" draggable="true" data-from="unlinked" data-type="${esc(u.类型)}" data-file="${esc(u.文件)}" data-j="${j}" title="${esc(u.文件)}">${esc(shortName(u.文件))} <em>${esc(u.类型)}</em></span>`).join("");
  $("unlinked").innerHTML = chips || `<div class="drag-hint">无认不准报告 ✓<br><small>把材质上挂错的也可拖回这里</small></div>`;
}

// ── 拖拽 ────────────────────────────────────────────────────
function bind() {
  document.querySelectorAll(".filechip").forEach((el) => {
    el.addEventListener("dragstart", (e) => {
      S.drag = { from: el.dataset.from, type: el.dataset.type, file: el.dataset.file };
      e.dataTransfer.effectAllowed = "move";
    });
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

function toggleExempt(i) {
  const m = S.bom.materials[i];
  if (m.豁免) { delete m.豁免; delete m.豁免原因; }
  else { const r = prompt("豁免原因（如 本料无第三方报告 / 源缺）:", "本料缺第三方报告"); if (!r) return; m.豁免 = true; m.豁免原因 = r; }
  save(); render();
}

function refresh() {
  const miss = filetreeMissing(S.bom);
  const exN = S.bom.materials.filter((m) => m.豁免).length;
  const unl = S.bom.unlinked_files.length;
  $("summary").textContent = miss.length
    ? "还差: " + miss.slice(0, 8).join(" · ") + (miss.length > 8 ? ` …共${miss.length}` : "")
    : `放置已齐（${S.bom.materials.length}材质${exN ? `·豁免${exN}` : ""}${unl ? `·待拖${unl}` : ""}）`;
  $("gatebtn").disabled = miss.length > 0;
}

function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api.filetreeSave(S.job, S.bom).catch(() => {}), 800);
}

async function onConfirm() {
  setBusy("提交…");
  try {
    await api.filetreeConfirm(S.job, S.bom);
    setBusy("");
    $("summary").textContent = "✅ 文件树已确认，进入第5步（照片）";
    $("gatebtn").disabled = true;
  } catch (e) { setBusy(""); alert("放行被拦：" + e.message); }
}

function shortName(s) { s = String(s || ""); return s.length > 22 ? s.slice(0, 20) + "…" : s; }
function setBusy(t) { $("busy").textContent = t; $("busy").style.display = t ? "block" : "none"; }
function esc(s) { return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

boot();
