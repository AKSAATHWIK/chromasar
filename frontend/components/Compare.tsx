"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { ZoomPan } from "@/lib/useZoomPan";

/** Drag-to-compare: base image under, generated layer clipped above.
 *
 * Both halves render inside the SAME transform, so zooming or panning moves them
 * together and they cannot drift out of registration - comparing two images that are
 * not aligned to the same pixel is worse than not comparing them at all.
 *
 * The split itself stays in screen space: it is a curtain drawn across the viewport,
 * not a feature of the imagery, so it must not scale with the zoom. That is why the
 * clip-path lives on the untransformed `.top` wrapper and the transform is applied to
 * the content inside it.
 */
export function Compare({ base, top, leftLabel, rightLabel, zoom }: {
  base: ReactNode; top: ReactNode; leftLabel: string; rightLabel: string;
  zoom?: ZoomPan;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [split, setSplit] = useState(50);
  const [drag, setDrag] = useState(false);
  const [misaligned, setMisaligned] = useState(false);

  /* Sharing one transform aligns the two halves ONLY while they letterbox identically.
     Both sit in the same box with object-fit:contain, so the painted area is decided by
     each source's intrinsic aspect ratio - two sources of different shape would share a
     transform and still paint at different offsets. That is silent misregistration, and
     in a comparison tool a quiet 3-pixel offset is worse than a visible failure: you
     would read it as a real difference between the two images. Check and say so. */
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => {
      // Branch on the element type, never `canvas.width || img.naturalWidth`: on an
      // <img>, `.width` is the RENDERED layout width, not the intrinsic one, so that
      // shortcut compared a 899x427 layout box against a 512x512 canvas and reported
      // every correctly-aligned pair as misaligned.
      const ar = [...el.querySelectorAll<HTMLElement>(".cmphalf > *")].map((n) => {
        const w = n instanceof HTMLCanvasElement ? n.width
          : n instanceof HTMLImageElement ? n.naturalWidth : 0;
        const h = n instanceof HTMLCanvasElement ? n.height
          : n instanceof HTMLImageElement ? n.naturalHeight : 0;
        return w && h ? w / h : null;
      }).filter((v): v is number => v !== null);
      setMisaligned(ar.length === 2 && Math.abs(ar[0] - ar[1]) > 0.01);
    };
    check();
    const imgs = [...el.querySelectorAll("img")];
    imgs.forEach((i) => i.addEventListener("load", check));
    return () => imgs.forEach((i) => i.removeEventListener("load", check));
  });

  const set = (clientX: number) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    setSplit(Math.max(0, Math.min(100, ((clientX - r.left) / r.width) * 100)));
  };

  /* A drag must end at the WINDOW, not at this element.
     onPointerUp/onPointerLeave on the div only fire if the release happens over the
     div. Let go past the edge of the image, outside the browser window, or after a
     setPointerCapture that threw, and the element never hears pointerup - so `drag`
     stays true and the curtain keeps tracking the mouse with no button held down.
     That is the "stuck slider": nothing is broken, the drag simply never ended.
     Tracking on the window also means the curtain keeps following while your cursor
     is outside the frame, which is what you expect when you overshoot. */
  useEffect(() => {
    if (!drag) return;
    const move = (e: PointerEvent) => set(e.clientX);
    const end = () => setDrag(false);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
    window.addEventListener("blur", end);          // alt-tab mid-drag
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
      window.removeEventListener("blur", end);
    };
  }, [drag]);

  const t = zoom ? { transform: zoom.transform, transformOrigin: "center center" } : undefined;

  return (
    <div
      ref={ref}
      className={`compare on ${drag ? "dragging" : ""} ${zoom?.panning ? "panning" : ""}`}
      style={{ ["--split" as string]: `${split}%` }}
      onPointerDown={(e) => {
        // Zoomed in, the drag gesture belongs to panning - otherwise you can never
        // reach the part of the image you just magnified. The curtain is still
        // movable by its handle, which claims the event before this fires.
        if (zoom?.zoomed && zoom.startPan(e)) return;
        setDrag(true);
        // capture is an optimisation - it keeps the drag alive outside the element.
        // It throws for a pointer id the element never saw, and an uncaught throw here
        // would abort the handler BEFORE the curtain moves, so the click does nothing.
        try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* not fatal */ }
        set(e.clientX);
      }}
      onPointerMove={(e) => { if (!drag) zoom?.movePan(e); }}
      onDoubleClick={() => zoom?.reset()}
    >
      <div className="cmphalf" style={t}>{base}</div>
      <div className="top"><div className="cmphalf" style={t}>{top}</div></div>
      <div
        className="handle"
        onPointerDown={(e) => {
          // the curtain always wins over panning, at any zoom level
          e.stopPropagation();
          setDrag(true);
          try {
            (e.currentTarget.parentElement as HTMLElement)
              .setPointerCapture(e.pointerId);
          } catch { /* see above */ }
          set(e.clientX);
        }}
      />
      {misaligned && (
        <div className="misfit">
          These two layers have different aspect ratios, so they cannot be registered to
          each other — read any apparent offset as an artefact, not a real change.
        </div>
      )}
      <div className="lbl l">{leftLabel}</div>
      <div className="lbl r">{rightLabel}</div>
    </div>
  );
}
