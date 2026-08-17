"use client";
import type { ReactNode } from "react";
import type { ZoomPan as ZoomPanState } from "@/lib/useZoomPan";

/** The pannable surface for the non-compare layers.
 *
 * This used to own its own zoom state AND render as an absolutely positioned wrapper
 * across the whole stage regardless of whether it was active - which meant that in
 * compare mode it sat invisibly on top of the compare widget and swallowed every
 * pointer event. State now lives in useZoomPan() above the layers, and this component
 * only mounts when its layers are the ones on screen.
 */
export function ZoomPan({ children, zoom, active }: {
  children: ReactNode; zoom: ZoomPanState; active: boolean;
}) {
  if (!active) return null;          // never overlay a layer that is not showing
  return (
    <div className="zoomwrap">
      {/* zoom.ref stays on the .stage, which is always mounted - hanging it here would
          kill wheel-zoom the moment compare mode unmounted this component */}
      <div
        className="zoomview"
        style={{ cursor: !zoom.zoomed ? "default" : zoom.panning ? "grabbing" : "grab" }}
        onDoubleClick={zoom.reset}
        onPointerDown={(e) => zoom.startPan(e)}
      >
        <div className="zoominner" style={{ transform: zoom.transform }}>
          {children}
        </div>
      </div>
    </div>
  );
}

/** Zoom readout and buttons. Rendered once per viewer, next to the stage. */
export function ZoomControls({ zoom }: { zoom: ZoomPanState }) {
  return (
    <div className="zoomctl">
      <button onClick={() => zoom.zoomAt(1.4)} aria-label="zoom in">+</button>
      <button onClick={() => zoom.zoomAt(1 / 1.4)} aria-label="zoom out">−</button>
      <button onClick={zoom.reset} aria-label="reset zoom" disabled={!zoom.zoomed}>⤢</button>
      <span className="zlvl">{zoom.z.toFixed(1)}×</span>
    </div>
  );
}
