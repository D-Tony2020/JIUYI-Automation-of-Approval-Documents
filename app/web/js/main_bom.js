// 确认环③ BOM脊柱编辑器 编排(files-first·B提议)。独立于确认环① main.js。
import * as api from "./api.js";
import { groupByPart, detectDups, suspect, allMissing, materialMissing, cardState } from "./bomstate.js";

const CATEGORIES = ["线材", "胶座", "端子", "套管", "锡丝", "油墨", "标签", "胶水", "镀层", "其他"];
const S = { job: null, materials: [], view: { group: true, filter: null, q: "" }, expanded: new Set() };
const $ = (id) => document.getElementById(id);
let saveTimer = null;

async function boot() {
  const job = new URLSearchParams(location.search).get("job");
  $("file").addEventListener("change", onUpload);
  if (job) {
    S.job = job;
    try {
      const s = await api.getBomState(job); S.materials = s.materials || [];
      const exp = new URLSearchParams(location.search).get("exp"); if (exp) S.expanded.add(+exp);  // 深链到某材质的核对块
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
  afterExtract();
}

function afterExtract() {
  setBusy("");
  $("uploadbar").style.display = "none";
  $("workspace").style.display = "block";
  render();
}

// ── 渲染 ────────────────────────────────────────────────────
function parts() { return [...new Set(S.materials.map((m) => (m.零件 || "").trim()).filter(Boolean))]; }

function render() {
  renderToolbar();
  const { parts: grp, order, unclaimed } = groupByPart(S.materials);
  const dups = detectDups(S.materials);
  const dupOf = {}; dups.forEach((g, k) => g.forEach((i) => (dupOf[i] = k)));
  let html = "";
  if (unclaimed.length) {
    html += `<div class="unclaimed"><div class="part-head warn">⚠ 待认领零件 ${unclaimed.length} 件（必须全部归零件才能放行）</div>`
      + unclaimed.filter(passFilter).map((i) => card(i, dupOf)).join("") + `</div>`;
  }
  if (S.view.group) {
    for (const p of order) {
      const idxs = grp[p].filter(passFilter);
      const sup = [...new Set(grp[p].map((i) => S.materials[i].供应商).filter(Boolean))];
      html += `<div class="part-group"><div class="part-head">▸ ${esc(p)} <small>${grp[p].length}件 · ${esc(sup.join("/"))||"供应商待填"}</small></div>`
        + idxs.map((i) => card(i, dupOf)).join("") + `</div>`;
    }
  } else {
    html += S.materials.map((m, i) => i).filter((i) => S.materials[i].零件 && passFilter(i)).map((i) => card(i, dupOf)).join("");
  }
  $("bomtable").innerHTML = html || "<p class='tip'>无匹配材质</p>";
  bind();
  refresh();
}

function passFilter(i) {
  const m = S.materials[i];
  if (S.view.filter === "todo" && materialMissing(m, i).length === 0) return false;
  if (S.view.filter === "warn" && suspect(m).length === 0) return false;
  if (S.view.q) {
    const q = S.view.q.toLowerCase();
    if (![m.材质, m.供应商, m.源文件].some((x) => String(x || "").toLowerCase().includes(q))) return false;
  }
  return true;
}

function card(i, dupOf) {
  const m = S.materials[i], st = cardState(m, i), reasons = suspect(m), open = S.expanded.has(i);
  const partOpts = ['<option value="">← 选零件</option>']
    .concat(parts().map((p) => `<option ${m.零件 === p ? "selected" : ""}>${esc(p)}</option>`))
    .concat('<option value="__new__">➕ 新建零件…</option>').join("");
  const catOpts = ['<option value="">← 类别</option>']
    .concat(CATEGORIES.map((c) => `<option ${m.材质类别 === c ? "selected" : ""}>${c}</option>`)).join("");
  const sup = (m.供应商 || "").trim();
  const supSt = !sup ? "todo" : (m.供应商原文 && sup !== m.供应商原文 && _aliased(m) ? "ok" : "warn");
  return `<div class="card mat-card ${m.手补 ? "manual" : ""}" data-st="${st}" data-i="${i}">
    ${m.手补 ? '<div class="manual-tag">手动补 · 无MSDS</div>' : ""}
    ${dupOf[i] !== undefined ? '<div class="dup-tag">⚠ 检测到同名材质，是同一料的重复上传吗？<button data-merge="' + dupOf[i] + '">合并</button> <button data-keepdup="' + dupOf[i] + '">都保留</button></div>' : ""}
    <div class="mat-row">
      <input type="checkbox" data-sel="${i}">
      <span class="matname" title="B抽取，可改">${esc(m.材质) || "(空)"}</span>
      <select class="inp part-sel ${m.零件 ? "" : "need"}" data-part="${i}">${partOpts}</select>
      <select class="inp" data-cat="${i}">${catOpts}</select>
      <input class="inp sup sup-${supSt}" data-sup="${i}" value="${esc(sup)}" placeholder="供应商">
      <span class="pill">成分${(m.成份 || []).length}·${reasons.length ? "⚠" + reasons.length : "RoHS"}</span>
      <label class="chk"><input type="checkbox" data-chk="${i}" ${m.已核对 ? "checked" : ""} ${m.豁免 ? "disabled" : ""}> 已核对</label>
      <button class="exbtn" data-exempt="${i}">${m.豁免 ? "取消豁免" : "豁免"}</button>
      <button class="expbtn" data-exp="${i}">${open ? "收起▴" : "核对▾"}</button>
    </div>
    ${open ? block(i, reasons) : ""}
  </div>`;
}

function _aliased(m) { return true; }   // 三态简化: 有值即视已确认(真别名命中由后端 normalize_supplier 保证)

function block(i, reasons) {
  const m = S.materials[i];
  const comps = (m.成份 || []).slice(0, 6).map((c) =>
    `<tr><td>${esc(c.成份名称)}</td><td>${esc(c.CAS)}</td><td>${esc(c["重量%"])}</td></tr>`).join("");
  const ro = Object.entries(m.RoHS || {}).map(([k, v]) => {
    const bad = v && !["ND", "NA", ""].includes(String(v).toUpperCase());
    return `<span class="rohs-pill ${bad ? "bad" : "ok"}">${k}:${esc(v) || "—"}</span>`;
  }).join("");
  return `<div class="block ${reasons.length ? "warn" : ""}">
    <div class="block-head">报告 ${esc(m.报告编号) || "(无报告号)"} · ${esc(m.报告日期) || "—"} · 源:${esc(m.源文件) || "—"}</div>
    ${reasons.length ? `<div class="block-warn">⚠ 此块请务必核对：${reasons.join("、")}</div>` : ""}
    <table class="comp"><tr><th>成份</th><th>CAS</th><th>重量%</th></tr>${comps}</table>
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
    <input id="search" placeholder="搜索 材质/供应商/源文件" value="${esc(S.view.q)}">`;
  $("addmanual").onclick = addManual;
  $("batchpart").onchange = (e) => batchAssign(e.target.value);
  $("grouptoggle").onchange = (e) => { S.view.group = e.target.checked; render(); };
  $("ftodo").onchange = (e) => { S.view.filter = e.target.checked ? "todo" : null; render(); };
  $("fwarn").onchange = (e) => { S.view.filter = e.target.checked ? "warn" : null; render(); };
  $("search").oninput = (e) => { S.view.q = e.target.value; render(); };
}

// ── 事件 ────────────────────────────────────────────────────
function bind() {
  document.querySelectorAll("[data-part]").forEach((el) => el.onchange = () => setPart(+el.dataset.part, el.value));
  document.querySelectorAll("[data-cat]").forEach((el) => el.onchange = () => { S.materials[+el.dataset.cat].材质类别 = el.value; save(); refresh(); });
  document.querySelectorAll("[data-sup]").forEach((el) => el.oninput = () => { S.materials[+el.dataset.sup].供应商 = el.value; save(); markCard(+el.dataset.sup); });
  document.querySelectorAll("[data-chk]").forEach((el) => el.onchange = () => { S.materials[+el.dataset.chk].已核对 = el.checked; save(); render(); });
  document.querySelectorAll("[data-exp]").forEach((el) => el.onclick = () => { const i = +el.dataset.exp; S.expanded.has(i) ? S.expanded.delete(i) : S.expanded.add(i); render(); });
  document.querySelectorAll("[data-exempt]").forEach((el) => el.onclick = () => toggleExempt(+el.dataset.exempt));
  document.querySelectorAll("[data-merge]").forEach((el) => el.onclick = () => mergeDup(+el.dataset.merge));
  document.querySelectorAll("[data-keepdup]").forEach((el) => el.onclick = () => { /* 都保留: 解联标(本版仅视觉, 各自归零件即可) */ });
  $("gatebtn").onclick = onConfirm;
}

function setPart(i, val) {
  if (val === "__new__") { const p = prompt("新建零件名（如 导线 / 胶座端子 / 热缩管 / 锡）:"); if (!p) { render(); return; } S.materials[i].零件 = p.trim(); }
  else S.materials[i].零件 = val;
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
  S.materials.push({ 材质: "", 供应商: "", 成份: [], RoHS: {}, 零件: "", 材质类别: "", 已核对: false, 手补: true });
  render();
}

function toggleExempt(i) {
  const m = S.materials[i];
  if (m.豁免) { delete m.豁免; delete m.豁免原因; }
  else { const r = prompt("豁免原因（如 本料无MSDS已附REACH / 源PDF缺失）:", "本料无MSDS"); if (!r) { render(); return; } m.豁免 = true; m.豁免原因 = r; m.已核对 = false; }
  save(); render();
}

function mergeDup(k) {
  const g = detectDups(S.materials)[k]; if (!g) return;
  const keep = g[0];                                  // 主条=第一条(成分多者更佳, 本版取首条)
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

function markCard(i) { const c = document.querySelector(`.card[data-i="${i}"]`); if (c) c.dataset.st = cardState(S.materials[i], i); }

function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api.bomSave(S.job, { materials: S.materials }).catch(() => {}), 800);
}

async function onConfirm() {
  setBusy("提交…");
  try { await api.bomConfirm(S.job, { materials: S.materials }); $("summary").textContent = "✅ BOM脊柱已确认，进入第4步（文件树确认环②）"; $("gatebtn").disabled = true; }
  catch (e) { setBusy(""); alert("放行被拦：" + e.message); }
}

function setBusy(t) { $("busy").textContent = t; $("busy").style.display = t ? "block" : "none"; }
function esc(s) { return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

boot();
