// 实时重算 — 与 hitl/fai.spec_limits 口径**字节对齐**(口径漂移=灾难)。
// 真值单元 = (中心 c, 上公差 up, 下公差 lo)。
//   LSL = c − lo ; USL = c + up ; 中点 = (LSL+USL)/2。
// 非对称(up≠lo)时 中点≠c; 对称(up==lo)是 中点==c 的特例。
// 对应 hitl/fai.py:spec_limits —— 任何一边改公式, tests/test_recompute_parity 红灯。

export function trimInt(x) {
  // 整数值去浮点尾(98.0→98), 与 hitl.fai._maybe_int 一致; 否则保留(6位防累积误差)
  if (typeof x !== "number" || Number.isNaN(x)) return x;
  return Number.isInteger(x) ? x : Math.round(x * 1e6) / 1e6;
}

export function deriveLimits(c, up, lo) {
  const lsl = c - lo;
  const usl = c + up;
  const mid = (lsl + usl) / 2;
  return { lsl: trimInt(lsl), usl: trimInt(usl), mid: trimInt(mid) };
}
