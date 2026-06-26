// M2.5 导出页纯逻辑(可 node 单测): 软预警已知悉汇总。全软门——勾已知悉留痕, 不强制阻断。
export function ackKey(w) {
  return (w.类型 || "") + "|" + (w.文案 || "");
}

export function pendingAcks(warnings, acked) {
  const set = new Set(acked || []);
  return (warnings || []).filter((w) => !set.has(ackKey(w)));
}

export function exportSummary(warnings, acked) {
  const w = warnings || [];
  const pend = pendingAcks(w, acked).length;
  return { total: w.length, pending: pend, acked: w.length - pend };
}
