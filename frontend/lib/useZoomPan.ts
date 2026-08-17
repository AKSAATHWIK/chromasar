"use client";
import { useCallback, useEffect, useRef, useState } from "react";

/** One zoom/pan state for a whole viewer, shared by every layer including compare.
 *
 * The old design gave each `<ZoomPan>` its own state and rendered it as an absolutely
 * positioned wrapper over the entire stage. Two bugs fell out of that:
 *
 *  1. In compare mode the wrapper was `disabled` but still present, still `inset:0`,
 *     and still LAST in DOM order - so it painted over the compare widget and ate every
 *     pointer event. `elementFromPoint` at the centre of the stage returned `.zoominner`.
 *     The split slider could not be dragged and there was no zoom either, because zoom
 *     was disabled on that layer. Nothing worked at all.
 *  2. Zoom reset every time you switched layers, which defeats the one task the layer
 *     row exists for: flicking between colorized / truth / confidence on the SAME patch.
 *
 * State lives here, above the layers, so a single transform drives all of them. In
 * compare mode both halves receive the identical transform, so zooming one zooms the
 * other by construction - they cannot drift out of registration.
 */
export type ZoomPan = ReturnType<typeof useZoomPan>;

export function useZoomPan(max = 12) {
  const ref = useRef<HTMLDivElement>(null);
  const [z, setZ] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [panning, setPanning] = useState(false);
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  /** never let the image be dragged off its own frame */
  const clamp = useCallback((nz: number, p: { x: number; y: number }) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return p;
    const mx = (r.width * (nz - 1)) / 2;
    const my = (r.height * (nz - 1)) / 2;
    return { x: Math.max(-mx, Math.min(mx, p.x)), y: Math.max(-my, Math.min(my, p.y)) };
  }, []);

  const zoomAt = useCallback((factor: number, clientX?: number, clientY?: number) => {
    const r = ref.current?.getBoundingClientRect();
    setZ((cur) => {
      const nz = Math.max(1, Math.min(max, cur * factor));
      if (nz === 1) { setPos({ x: 0, y: 0 }); return nz; }
      if (r && clientX !== undefined && clientY !== undefined) {
        // keep the pixel under the cursor pinned - this is what makes it feel like a
        // map tool rather than a slideshow
        const cx = clientX - r.left - r.width / 2;
        const cy = clientY - r.top - r.height / 2;
        const k = nz / cur;
        setPos((p) => clamp(nz, { x: cx - (cx - p.x) * k, y: cy - (cy - p.y) * k }));
      } else {
        setPos((p) => clamp(nz, p));
      }
      return nz;
    });
  }, [clamp, max]);

  /* React attaches `wheel` at the root as a PASSIVE listener, so preventDefault() inside
     a JSX onWheel handler is ignored and the workspace scrolls underneath while you are
     trying to zoom. It has to be a manually registered non-passive listener. */
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const h = (e: WheelEvent) => {
      e.preventDefault();
      zoomAt(e.deltaY < 0 ? 1.18 : 1 / 1.18, e.clientX, e.clientY);
    };
    el.addEventListener("wheel", h, { passive: false });
    return () => el.removeEventListener("wheel", h);
  }, [zoomAt]);

  const reset = useCallback(() => { setZ(1); setPos({ x: 0, y: 0 }); }, []);

  const startPan = useCallback((e: React.PointerEvent) => {
    if (z <= 1) return false;                 // at 1x there is nothing to pan
    drag.current = { x: e.clientX, y: e.clientY, ox: pos.x, oy: pos.y };
    setPanning(true);
    try { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); }
    catch { /* capture is an optimisation, never a precondition for panning */ }
    return true;
  }, [z, pos]);

  const movePan = useCallback((e: React.PointerEvent) => {
    if (!drag.current) return;
    setPos(clamp(z, {
      x: drag.current.ox + (e.clientX - drag.current.x),
      y: drag.current.oy + (e.clientY - drag.current.y),
    }));
  }, [clamp, z]);

  const endPan = useCallback(() => { drag.current = null; setPanning(false); }, []);

  /* Same failure mode as the compare curtain: a pan released outside the viewport left
     `panning` true, so the image kept sliding under a mouse with no button pressed.
     The window is the only surface guaranteed to see the release. */
  useEffect(() => {
    if (!panning) return;
    const move = (e: PointerEvent) => {
      if (!drag.current) return;
      setPos(clamp(z, {
        x: drag.current.ox + (e.clientX - drag.current.x),
        y: drag.current.oy + (e.clientY - drag.current.y),
      }));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", endPan);
    window.addEventListener("pointercancel", endPan);
    window.addEventListener("blur", endPan);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", endPan);
      window.removeEventListener("pointercancel", endPan);
      window.removeEventListener("blur", endPan);
    };
  }, [panning, clamp, z, endPan]);

  return {
    ref, z, pos, panning, reset, zoomAt, startPan, movePan, endPan,
    /** the single source of truth every layer renders with */
    transform: `translate(${pos.x}px, ${pos.y}px) scale(${z})`,
    zoomed: z > 1,
  };
}
