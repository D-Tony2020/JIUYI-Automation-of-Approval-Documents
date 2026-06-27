// 共享步条(四页一字不差): 删②选型→四步①核对图纸②理材质③挂文件④照片导出。
// done步可点回看(?job=), 当前高亮, 缺N徽标(setBadges, 数据来自 /api/overview)。来自 UXUI 设计评审。
import * as api from "./api.js";

export const STEPS = [
  { n: 1, label: "核对图纸", page: "index.html" },
  { n: 2, label: "理材质", page: "index_bom.html" },
  { n: 3, label: "挂文件", page: "index_filetree.html" },
  { n: 4, label: "照片导出", page: "index_export.html" },
];
const NUM = ["", "①", "②", "③", "④"];

function _job() {
  return new URLSearchParams(location.search).get("job") || "";
}

function _favicon() {
  if (document.querySelector("link[rel=icon]")) return;
  const l = document.createElement("link"); l.rel = "icon"; l.href = "favicon.svg"; document.head.appendChild(l);
}

export function renderSteps(containerId, cur) {
  _favicon();
  const el = document.getElementById(containerId);
  if (!el) return;
  const job = _job();
  const brand = `<span class="brand-logo" title="久益 · 材料承认书自动生成(给生久供货)">久益 AI</span>`;
  const home = `<a class="home-link" href="index_home.html" title="返回历史记录">← 本单</a>`;
  el.innerHTML = brand + home + STEPS.map((s) => {
    const cls = s.n === cur ? "cur" : (s.n < cur ? "done" : "");
    const click = s.n !== cur && job;                 // 非当前步可点跳(回看/续做)
    const inner = `${NUM[s.n]}${s.label}<span class="bdg" data-bdg="${s.n}"></span>`;
    return click
      ? `<a class="step ${cls}" href="${s.page}?job=${encodeURIComponent(job)}">${inner}</a>`
      : `<span class="step ${cls}">${inner}</span>`;
  }).join("");
  loadBadges(cur);                                     // 异步拉总进度填缺N徽标
}

async function loadBadges(cur) {
  const job = _job();
  if (!job) return;
  let ov;
  try { ov = await api.overview(job); } catch { return; }
  for (const s of STEPS) {
    const b = document.querySelector(`[data-bdg="${s.n}"]`);
    if (!b) continue;
    const stepEl = b.closest(".step");
    const o = (ov && ov[s.n]) || null;
    if (!o || o.缺 == null) { b.textContent = ""; b.className = "bdg"; continue; }
    if (o.缺 > 0) {                                  // 已访问但未齐→琥珀"未完成"(非绿done), 挂缺N
      b.textContent = "缺" + o.缺; b.className = "bdg miss";
      if (stepEl && s.n !== cur) { stepEl.classList.remove("done"); stepEl.classList.add("incomplete"); }
    } else {                                         // 齐→绿✓
      b.textContent = "✓"; b.className = "bdg ok";
      if (stepEl && s.n !== cur) { stepEl.classList.remove("incomplete"); stepEl.classList.add("done"); }
    }
  }
}
