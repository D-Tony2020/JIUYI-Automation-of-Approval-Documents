// 共享放行门(软导航式, 老板拍板): summary→可点待办chips(红硬/橙软), 放行键常可点;
// 未达态点击不跳转而是滚到第一个待办+闪烁; 门旁固定软硬话术。来自 UXUI 设计评审 P0.3。

function esc(s) {
  return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));
}

export function flash(el) {
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 1200);
}

export function scrollFirstTodo(selector) {
  flash(document.querySelector(selector));
}

/* opts: {summaryId, btnId, missing:[{t,hard}], doneText, nextLabel, rule, todoSel} → 渲染门。
   返回 {hardLeft} 供 onConfirm 判断是否放行。常可点; 阻塞时 onConfirm 自行 scrollFirstTodo。 */
export function renderGate(opts) {
  const sum = document.getElementById(opts.summaryId);
  const btn = document.getElementById(opts.btnId);
  const miss = opts.missing || [];
  const hardLeft = miss.filter((m) => m.hard).length;
  if (sum) {
    const rule = opts.rule ? `<span class="gate-rule">${esc(opts.rule)}</span>` : "";
    if (miss.length) {
      const chips = miss.slice(0, 10).map((m, i) =>
        `<span class="todo-chip ${m.hard ? "hard" : "soft"}" data-todo="${i}" title="点击定位">${esc(m.t)}</span>`).join("");
      sum.innerHTML = chips + (miss.length > 10 ? `<span class="todo-chip more">…共${miss.length}</span>` : "") + rule;
      if (opts.todoSel) {
        sum.querySelectorAll("[data-todo]").forEach((c) => (c.onclick = () => scrollFirstTodo(opts.todoSel)));
      }
    } else {
      sum.innerHTML = `<span class="gate-ok">✓ ${esc(opts.doneText || "本步已齐")}</span>` + rule;
    }
  }
  if (btn) {
    btn.disabled = false;                              // 软导航: 常可点
    btn.textContent = opts.nextLabel || "下一步 →";
    btn.classList.toggle("blocked", hardLeft > 0);     // 有硬门→视觉警示(琥珀)但仍可点
  }
  return { hardLeft, softLeft: miss.length - hardLeft };
}
