// 图纸查看器: 滚轮缩放 / 拖拽平移 / 双击复位 / 翻页。图纸是本环视觉重心。

export function mountViewer(container, job, pages) {
  let n = 0, scale = 1, tx = 0, ty = 0, dragging = false, sx = 0, sy = 0;
  container.innerHTML = "";
  const stage = document.createElement("div");
  stage.className = "viewer-stage";
  const img = document.createElement("img");
  img.className = "viewer-img";
  img.draggable = false;
  stage.appendChild(img);
  container.appendChild(stage);

  // 翻页条
  const bar = document.createElement("div");
  bar.className = "viewer-pagebar";
  container.appendChild(bar);

  function apply() {
    img.style.transform = `translate(${tx}px,${ty}px) scale(${scale})`;
  }
  function load() {
    img.src = `/api/drawing/${job}/page/${n}.png`;
    bar.innerHTML = "";
    for (let i = 0; i < pages; i++) {
      const b = document.createElement("button");
      b.textContent = `第${i + 1}页`;
      b.className = i === n ? "pg active" : "pg";
      b.onclick = () => { n = i; reset(); load(); };
      bar.appendChild(b);
    }
  }
  function reset() { scale = 1; tx = 0; ty = 0; apply(); }

  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    const f = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    scale = Math.min(8, Math.max(0.3, scale * f));
    apply();
  }, { passive: false });
  stage.addEventListener("mousedown", (e) => { dragging = true; sx = e.clientX - tx; sy = e.clientY - ty; });
  window.addEventListener("mousemove", (e) => { if (dragging) { tx = e.clientX - sx; ty = e.clientY - sy; apply(); } });
  window.addEventListener("mouseup", () => { dragging = false; });
  stage.addEventListener("dblclick", reset);

  load();
  return { goPage: (i) => { n = i; reset(); load(); } };
}
