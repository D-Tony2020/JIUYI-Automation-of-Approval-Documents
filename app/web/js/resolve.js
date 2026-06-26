// 材质为锚解析(镜像 hitl/dicts.resolve_material), 纯逻辑可 node 单测。
// 改材质名 → 标准名(简称字典规范化包含匹配) → 材质类别/零件(反查字典)。

export function norm(s) {
  return String(s == null ? "" : s).replace(/\s+/g, "").toUpperCase();
}

export function stdName(原文, alias) {
  const h = norm(原文);
  let best = null, bl = 0;
  for (const [std, toks] of Object.entries(alias || {})) {
    for (const t of toks || []) {
      const tn = norm(t);
      if (tn && h.includes(tn) && tn.length > bl) { best = std; bl = tn.length; }
    }
  }
  return best || String(原文 == null ? "" : 原文).trim();
}

export function resolveMaterial(原文, alias, catpart) {
  const std = stdName(原文, alias || {});
  const info = (catpart || {})[std] || {};
  return { 标准名: std, 材质类别: info.材质类别 || "", 零件: info.零件 || "" };
}
