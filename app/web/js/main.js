// 确认环① 编排: 上传→抽取→渲染(图纸+三要素+FAI卡)+实时重算+放行门。
import * as api from "./api.js";
import { deriveLimits } from "./recompute.js";
import { mountViewer } from "./viewer.js";
import { checkVersion, checkCode, checkName, checkDim } from "./rules.js";
import { renderGate, scrollFirstTodo } from "./gate.js";
import { dlgPrompt } from "./dialog.js";

const S = { job: null, data: null, pages: 1 };

const $ = (id) => document.getElementById(id);

async function boot() {
  const job = new URLSearchParams(location.search).get("job");
  $("file").addEventListener("change", onUpload);
  if (job) {
    try { S.job = job; S.data = await api.getState(job); await afterExtract(); }
    catch { /* 未抽取, 等上传 */ }
  }
}

async function onUpload(e) {
  const f = e.target.files[0];
  if (!f) return;
  setBusy("上传中…");
  const up = await api.uploadDrawing(f);
  S.job = up.job_id; S.pages = up.pages;
  history.replaceState(null, "", "?job=" + encodeURIComponent(S.job));   // job 写URL, 跨页带得走
  setBusy("qwen-vl 读图中(首次约 10–20 秒)…");
  S.data = await api.extract(S.job);
  await afterExtract();
}

async function afterExtract() {
  S.pages = S.pages || 1;
  $("uploadbar").style.display = "none";
  $("workspace").style.display = "flex";
  $("dwgname").textContent = (S.data.名称 || "") + " · " + (S.data.品号 || "");
  mountViewer($("viewer"), S.job, S.pages);
  S.data.checked = S.data.checked || {};
  renderRight();
}

// ── 右栏渲染 ────────────────────────────────────────────────
function renderRight() {
  const d = S.data;
  const ids = [
    ["品号", d.品号, checkCode, "→封面D14"],
    ["版本", d.版本, checkVersion, "→封面D16"],
    ["名称", d.名称, checkName, "→封面D12品类"],
  ];
  $("identity").innerHTML = ids.map((x, i) => idCard(i, x)).join("");
  $("dims").innerHTML = d.dimensions.map((dim, i) => dimCard(i, dim)).join("");
  bindEvents();
  refresh();
}

function idCard(i, [label, val, , hint]) {
  const key = "id" + i;
  return `<div class="card" data-key="${key}">
    <div class="card-row">
      <label class="lbl">${label}</label>
      <input class="inp" data-field="id" data-i="${i}" value="${esc(val ?? "")}">
      <span class="rule" id="rule-${key}"></span>
      <span class="hint">${hint}</span>
    </div>
    <label class="chk"><input type="checkbox" data-check="${key}" ${S.data.checked[key] ? "checked" : ""}> 已核对图纸</label>
  </div>`;
}

function dimCard(i, dim) {
  const key = "dim" + i;
  const exempt = (S.data.exemptions || []).some((e) => e.序号 === i);
  return `<div class="card ${exempt ? "exempt" : ""}" data-key="${key}">
    <div class="card-row">
      <span class="seq">尺寸 ${i + 1}</span>
      <input class="inp num" data-field="中心" data-i="${i}" value="${dim.中心 ?? ""}"> <span class="pm">±</span>
      <input class="inp num" data-field="上" data-i="${i}" value="${dim.上 ?? ""}">
      <span class="rule" id="rule-${key}"></span>
    </div>
    <div class="derived" id="derived-${key}"></div>
    <div class="card-row">
      <label class="chk"><input type="checkbox" data-check="${key}" ${S.data.checked[key] ? "checked" : ""} ${exempt ? "disabled" : ""}> 已核对图纸</label>
      <button class="exbtn" data-exempt="${i}">${exempt ? "取消豁免" : "豁免"}</button>
    </div>
  </div>`;
}

function bindEvents() {
  document.querySelectorAll(".inp").forEach((el) =>
    el.addEventListener("input", () => { writeBack(el); refresh(); }));
  document.querySelectorAll("[data-check]").forEach((el) =>
    el.addEventListener("change", () => { S.data.checked[el.dataset.check] = el.checked; refresh(); }));
  document.querySelectorAll("[data-exempt]").forEach((el) =>
    el.addEventListener("click", () => toggleExempt(+el.dataset.exempt)));
  $("gatebtn").addEventListener("click", onConfirm);
}

function writeBack(el) {
  const i = +el.dataset.i, f = el.dataset.field;
  if (f === "id") { const m = ["品号", "版本", "名称"]; S.data[m[i]] = el.value; }
  else { S.data.dimensions[i][f] = parseFloat(el.value); }
}

async function toggleExempt(i) {
  S.data.exemptions = S.data.exemptions || [];
  const at = S.data.exemptions.findIndex((e) => e.序号 === i);
  if (at >= 0) { S.data.exemptions.splice(at, 1); }
  else {
    const reason = await dlgPrompt({ title: "尺寸豁免原因(必填, 留痕)", presets: ["该尺寸非受检", "图纸未标公差", "客户豁免", "其他(填备注)"] });
    if (!reason) return;
    S.data.exemptions.push({ 序号: i, 原因: reason, ts: new Date().toISOString() });
    S.data.checked["dim" + i] = false;
  }
  renderRight();
}

// ── 实时重算 + 规则 + 放行门(单一 state 驱动三处恒一致) ──────
function refresh() {
  const d = S.data;
  let missing = [];
  // 三要素规则 + 勾核
  [["品号", checkCode, "id0"], ["版本", checkVersion, "id1"], ["名称", checkName, "id2"]].forEach(([k, fn, key]) => {
    const ok = fn(d[k]); markRule(key, ok);
    if (!ok) missing.push(`${k}格式`);
    if (!d.checked[key]) missing.push(`${k}未勾核`);
    markCard(key, ok ? (d.checked[key] ? "ok" : "todo") : "warn");
  });
  // 尺寸: 实时重算 + 规则 + 勾核/豁免
  d.dimensions.forEach((dim, i) => {
    const key = "dim" + i;
    const exempt = (d.exemptions || []).some((e) => e.序号 === i);
    const der = deriveLimits(dim.中心, dim.上, dim.下 ?? dim.上);
    $("derived-" + key).innerHTML = exempt ? "<i>已豁免</i>"
      : `LSL <b>${der.lsl}</b> · 中心 <b>${der.mid}</b> · USL <b>${der.usl}</b>`;
    const rok = checkDim(dim);
    markRule(key, rok);
    if (exempt) { markCard(key, "exempt"); return; }
    if (!rok) missing.push(`尺寸${i + 1}公差异常`);
    if (!d.checked[key]) missing.push(`尺寸${i + 1}未勾核`);
    markCard(key, rok ? (d.checked[key] ? "ok" : "todo") : "warn");
  });
  // 放行门(软导航式) + 待办chips
  const exN = (d.exemptions || []).length;
  S.missing = missing;
  renderGate({
    summaryId: "summary", btnId: "gatebtn",
    missing: missing.map((t) => ({ t, hard: true })),       // ①是硬门
    doneText: `三要素与FAI全部已核对${exN ? ` · 豁免${exN}` : ""}`,
    nextLabel: "三要素与FAI全部核对 → 第2步 理材质 →",
    rule: "硬门：缺项需先核对", todoSel: ".card[data-st='todo'],.card[data-st='warn']",
  });
}

function markRule(key, ok) { const e = $("rule-" + key); if (e) e.textContent = ok ? "✓" : "⚠"; if (e) e.className = "rule " + (ok ? "ok" : "warn"); }
function markCard(key, st) { const c = document.querySelector(`.card[data-key="${key}"]`); if (c) c.dataset.st = st; }

async function onConfirm() {
  if (S.missing && S.missing.length) {                       // 软导航: 未达→滚到第一个待办, 不跳转
    scrollFirstTodo(".card[data-st='todo'],.card[data-st='warn']");
    return;
  }
  setBusy("提交确认…");
  await api.confirm(S.job, { 品号: S.data.品号, 版本: S.data.版本, 名称: S.data.名称, dimensions: S.data.dimensions, exemptions: S.data.exemptions, checked: S.data.checked });
  const next = "index_bom.html?job=" + encodeURIComponent(S.job);
  $("summary").innerHTML = `✅ 已确认通过 · <a href="${next}">进入 ③BOM脊柱 →</a>`;
  $("gatebtn").disabled = true;
  setTimeout(() => { location.href = next; }, 900);
}

function setBusy(t) { $("busy").textContent = t; $("busy").style.display = t ? "block" : "none"; }
function esc(s) { return String(s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

boot();
