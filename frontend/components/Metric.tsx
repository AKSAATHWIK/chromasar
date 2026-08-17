"use client";
import { useEffect, useRef, useState } from "react";

/** Count-up metric tile.
 *  requestAnimationFrame is throttled to zero in hidden tabs, so a timeout guarantees
 *  the final value lands even when rAF never fires. */
export function Metric({ value, label, digits = 3, suffix = "", tone = "" }: {
  value: number | null; label: string; digits?: number; suffix?: string; tone?: string;
}) {
  const [text, setText] = useState("—");
  const prev = useRef(0);

  useEffect(() => {
    if (value === null || !isFinite(value)) { setText("—"); return; }
    const from = prev.current, to = value;
    prev.current = to;
    const final = to.toFixed(digits) + suffix;
    const t0 = performance.now(), dur = 420;
    let raf = 0;
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      setText((from + (to - from) * e).toFixed(digits) + suffix);
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    const fin = setTimeout(() => setText(final), dur + 60);
    return () => { cancelAnimationFrame(raf); clearTimeout(fin); };
  }, [value, digits, suffix]);

  return (
    <div className={`metric ${tone}`}>
      <div className="v num">{text}</div>
      <div className="k">{label}</div>
    </div>
  );
}
