// 断点续做首页: 最近本单列表(读 /api/orders) + 各步进度点 + 继续到续做步。来自 UXUI 评审。
import * as api from "./api.js";

const NUM = ["", "①", "②", "③", "④"];
const PAGE = { 1: "index.html", 2: "index_bom.html", 3: "index_filetree.html", 4: "index_export.html" };
const LBL = ["", "核对图纸", "理材质", "挂文件", "照片导出"];

function esc(s) { return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

function fmtTime(t) {
  try { const d = new Date(t * 1000); const p = (n) => String(n).padStart(2, "0"); return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`; } catch { return ""; }
}

async function boot() {
  if (!document.querySelector("link[rel=icon]")) { const l = document.createElement("link"); l.rel = "icon"; l.href = "favicon.svg"; document.head.appendChild(l); }
  const el = document.getElementById("orderlist");
  let list;
  try { list = await api.orders(); } catch (e) { el.innerHTML = `<p class="tip">读取失败：${esc(e.message)}</p>`; return; }
  if (!list.length) { el.innerHTML = `<div class="empty">暂无本单 · 点右上「+ 新建本单」开始</div>`; return; }
  el.innerHTML = list.map((o) => {
    const dots = [1, 2, 3, 4].map((n) => {
      const x = (o.overview || {})[n] || null;
      const cls = x ? (x.缺 > 0 ? "dot miss" : "dot ok") : "dot";
      return `<span class="${cls}" title="${LBL[n]}${x ? (x.缺 > 0 ? " 缺" + x.缺 : " ✓") : " 未开始"}">${NUM[n]}</span>`;
    }).join("");
    const status = o.exported
      ? `<span class="badge done">已导出</span>`
      : `<span class="badge ing">在第${o.resume}步 ${LBL[o.resume]}</span>`;
    const page = PAGE[o.resume] || "index.html";
    return `<div class="order-card">
      <div class="oc-main">
        <div class="oc-title">${esc(o.品号 || o.job)} <small>${esc(o.名称 || "")}</small></div>
        <div class="oc-steps">${dots} <span class="oc-time">更新 ${fmtTime(o.updated)}</span></div>
      </div>
      <div class="oc-right">${status}
        <a class="contbtn" href="${page}?job=${encodeURIComponent(o.job)}">${o.exported ? "查看" : "继续"} →</a></div>
    </div>`;
  }).join("");
}

boot();
