"use client";
import { useState } from "react";
import { Metric } from "./Metric";
import { ZoomPan, ZoomControls } from "./ZoomPan";
import { useZoomPan } from "@/lib/useZoomPan";
import { Compare } from "./Compare";

type ChangeResult = {
  before_vv: string; after_vv: string; change: string;
  water_before: string; water_after: string;
  stats: Record<string, number>;
  narrative: string[];
  size: [number, number];
  ms: number;
};

const LAYERS = [
  ["compare", "Before ⟷ After"], ["change", "Change map"],
  ["before", "Before"], ["after", "After"],
] as const;
type Layer = (typeof LAYERS)[number][0];

import { Drop } from "./Drop";
export function ChangeView() {
  const [before, setBefore] = useState<File | null>(null);
  const [after, setAfter] = useState<File | null>(null);
  const [thrDb, setThrDb] = useState(3);
  const [res, setRes] = useState<ChangeResult | null>(null);
  const zoom = useZoomPan();
  // the change rasters are whatever the user uploaded, so the ratio is read off the
  // decoded image rather than assumed square
  const [ar, setAr] = useState<number | null>(null);
  const [layer, setLayer] = useState<Layer>("compare");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const run = async () => {
    if (!before || !after) return;
    setBusy(true); setErr("");
    try {
      const fd = new FormData();
      fd.append("before", before);
      fd.append("after", after);
      const r = await fetch(`/api/change?thr_db=${thrDb}`, { method: "POST", body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail ?? "change detection failed");
      setRes(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const picker = (label: string, file: File | null,
                  set: (f: File | null) => void) => (
    <>
      <label>{label}</label>
      <Drop label="drop or click - 2-band SAR GeoTIFF" accept=".tif,.tiff"
        file={file} onFile={set} disabled={busy} />
    </>
  );

  const s = res?.stats;
  const img = { width: "100%", height: "100%", objectFit: "contain" as const,
                imageRendering: "pixelated" as const, display: "block" };

  return (
    <div className="layout">
      <aside>
        <div className="card">
          <h3>Two acquisitions</h3>
          {picker("Earlier date", before, setBefore)}
          {picker("Later date", after, setAfter)}
          <label>Change threshold <b>{thrDb} dB</b></label>
          <input type="range" min={1} max={8} value={thrDb}
            style={{ ["--pct" as string]: `${((thrDb - 1) / 7) * 100}%` }}
            onChange={(e) => setThrDb(+e.target.value)} />
          <button className="go" onClick={run} disabled={!before || !after || busy}>
            {busy ? <><span className="spin" />comparing</> : "Detect change"}
          </button>
          <div className="note tiny">
            Both scenes must cover the same footprint at the same size. SAR is already
            logarithmic, so the classic log-ratio is simply a difference in dB.
          </div>
        </div>

        {s && (
          <div className="card">
            <h3>Breakdown</h3>
            <table className="batch">
              <tbody>
                <tr><td>water before</td><td>{s.water_before_km2.toFixed(2)} km²</td></tr>
                <tr><td>water after</td><td>{s.water_after_km2.toFixed(2)} km²</td></tr>
                <tr><td>darkened</td><td>{s.darkened_km2.toFixed(2)} km²</td></tr>
                <tr><td>brightened</td><td>{s.brightened_km2.toFixed(2)} km²</td></tr>
                <tr><td>mean dB shift</td><td>{s.mean_db_shift.toFixed(2)} dB</td></tr>
              </tbody>
            </table>
          </div>
        )}
      </aside>

      <div>
        {err && <div className="warn"><div>{err}</div></div>}

        {s && (s.place || s.coords) && (
          <div className="place">
            <b>{(s.place as unknown as string) ?? "Location unknown"}</b>
            {s.coords && <span>{s.coords as unknown as string}</span>}
            {s.pixel_m2 && <span>· {Number(s.pixel_m2).toFixed(1)} m² per pixel</span>}
          </div>
        )}

        <div className="metrics">
          <Metric tone="lead" value={s ? s.new_water_km2 : null} label="New water"
            digits={2} suffix=" km²" />
          <Metric value={s ? s.receded_water_km2 : null} label="Receded"
            digits={2} suffix=" km²" />
          <Metric value={s ? s.net_water_change_km2 : null} label="Net change"
            digits={2} suffix=" km²" />
          <Metric value={res ? res.ms : null} label="Compute" digits={0} suffix=" ms" />
        </div>

        {/* Water as a share of the scene, both dates. This is the one cover class SAR
            measures well; vegetation and bare ground need the optical instrument and
            live on the Flood tab, which has a co-registered Sentinel-2 chip to read. */}
        {s && (
          <div className="card">
            <h3>Water cover, before and after</h3>
            <div className="cover">
              {([["water_before_pct", "Before", "#3d5a7a"],
                 ["water_after_pct", "After", "#3ec9ff"],
                 ["new_water_pct", "Newly flooded", "#ff6470"]] as const).map(
                ([k, lbl, col]) => (
                  <div key={k}>
                    <div className="coverrow">
                      <i className="sw" style={{ background: col }} />
                      <span className="nm">{lbl}</span>
                      <span className="pc">{Number(s[k] ?? 0).toFixed(2)}%</span>
                    </div>
                    <div className="coverbar" style={{ marginTop: 4 }}>
                      <i style={{ width: `${s[k] ?? 0}%`, background: col }} />
                    </div>
                  </div>
                ))}
            </div>
            <div className="note tiny mt">
              Percentages of the whole scene, from the flood model run on <b>both</b>
              dates. Only water is reported here: it is the one surface class radar
              measures reliably. Vegetation and bare ground are on the Flood tab, where a
              co-registered <b>Sentinel-2 optical</b> chip exists — an uploaded SAR pair
              has no optical counterpart, so those cannot be computed from it.
            </div>
          </div>
        )}

        <figure className="hero">
          <figcaption>
            <div className="layers">
              {LAYERS.map(([id, lbl]) => (
                <button key={id} className={layer === id ? "active" : ""}
                  onClick={() => setLayer(id)}>{lbl}</button>
              ))}
            </div>
            <span className="hint">
              scroll to zoom · drag to pan · double-click to reset
            </span>
          </figcaption>

          <div className="stage" ref={zoom.ref}
            style={ar ? { ["--ar" as string]: `${ar}` } : undefined}>
            {!res && <div className="empty">Load two SAR scenes of the same area</div>}
            {res && layer === "compare" && (
              <div className="pane on">
                <Compare leftLabel="before" rightLabel="after" zoom={zoom}
                  base={<img src={res.before_vv} alt="before"
                    onLoad={(e) => setAr(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight)} />}
                  top={<img src={res.after_vv} alt="after" />} />
              </div>
            )}
            {res && (
              <ZoomPan zoom={zoom} active={layer !== "compare"}>
                <img style={img} alt={layer}
                  onLoad={(e) => setAr(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight)}
                  src={layer === "change" ? res.change
                     : layer === "before" ? res.before_vv : res.after_vv} />
              </ZoomPan>
            )}
            {res && <ZoomControls zoom={zoom} />}
          </div>

          {res && (
            <div className="barfoot">
              <div className="legend">
                <span><i style={{ background: "#3dc8ff" }} />new water</span>
                <span><i style={{ background: "#ffa042" }} />receded</span>
                <span><i style={{ background: "#2a3546" }} />unchanged</span>
              </div>
              <span className="spacer" />
              <span className="chip">{res.size[0]}×{res.size[1]}</span>
            </div>
          )}
        </figure>

        {res && (
          <details className="card report-card" open>
            <summary>
              <h3 style={{ margin: 0 }}>Change report</h3>
              <span className="spacer" />
              <span className="chip">
                {s!.net_water_change_km2 >= 0 ? "expanding" : "receding"}
              </span>
            </summary>
            <ul className="report">
              {res.narrative.map((l, i) => <li key={i}>{l}</li>)}
            </ul>
          </details>
        )}

        <details className="card">
          <summary><h3 style={{ margin: 0 }}>How change detection works</h3></summary>
          <div className="note">
            SAR backscatter is measured in decibels, which are already logarithmic — so
            the standard <b>log-ratio</b> change operator reduces to a plain subtraction
            of the two dates. <b>Darkening</b> means the surface became smoother, which
            usually means new water. <b>Brightening</b> means it became rougher or gained
            a double-bounce structure — construction, or floodwater rising into
            vegetation. Separately, the same calibrated flood model scores both dates and
            the water masks are differenced, so the headline number is
            <b> water that is there now and was not there before</b> rather than total
            water. Because one model scores both dates, a difference reflects the ground
            and not a change of method.
          </div>
        </details>
      </div>
    </div>
  );
}
