"use client";
import { useEffect, useRef } from "react";

export function Histogram({ counts, cut, lo, hi }: {
  counts: number[]; cut: number; lo: string; hi: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c || !counts.length) return;
    const dpr = window.devicePixelRatio || 1;
    const w = c.clientWidth, h = c.clientHeight;
    if (!w) return;
    c.width = w * dpr; c.height = h * dpr;
    const g = c.getContext("2d")!;
    g.scale(dpr, dpr);
    g.clearRect(0, 0, w, h);
    const max = Math.max(...counts, 1);
    const bw = w / counts.length;
    counts.forEach((n, i) => {
      const bh = Math.pow(n / max, 0.42) * (h - 10);
      g.fillStyle = i / counts.length >= cut ? hi : lo;
      g.fillRect(i * bw, h - bh, Math.max(bw - 0.5, 0.6), bh);
    });
    g.strokeStyle = "#fff"; g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(cut * w, 0); g.lineTo(cut * w, h); g.stroke();
  }, [counts, cut, lo, hi]);
  return <canvas className="hist" ref={ref} />;
}
