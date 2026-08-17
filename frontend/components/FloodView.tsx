"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api, loadImage, toPixels, PIXEL_KM2,
  type Batch, type Report, type Cover,
} from "@/lib/api";
import { useHotkeys } from "@/lib/hotkeys";
import { Drop } from "./Drop";
import { CoverPanel } from "./CoverPanel";
import { Metric } from "./Metric";
import { Histogram } from "./Histogram";
import { Compare } from "./Compare";
import { ZoomPan, ZoomControls } from "./ZoomPan";
import { useZoomPan } from "@/lib/useZoomPan";

type Loaded = {
  name: string;
  prob: ImageData;
  label: ImageData | null;
  perm: ImageData | null;
  w: number; h: number;
  vv: string; vh: string;
  hist: number[];
  ms: number;
  /** true ground area of one pixel, m². Null when the source carries no
   *  georeferencing, in which case the nominal 100 m² is used and said so. */
  pixelM2: number | null;
};

const LAYERS = [
  ["compare", "Compare"], ["pred", "Detection"], ["agree", "Agreement"],
  ["vv", "SAR VV"], ["vh", "SAR VH"], ["perm", "Permanent"],
] as const;
type Layer = (typeof LAYERS)[number][0];

export function FloodView() {
  const [regions, setRegions] = useState<Record<string, string[]>>({});
  const [region, setRegion] = useState("");
  const [chip, setChip] = useState("");
  const [thr, setThr] = useState(0.5);
  const [excludePerm, setExcludePerm] = useState(true);
  const [layer, setLayer] = useState<Layer>("compare");
  const [data, setData] = useState<Loaded | null>(null);
  const [cover, setCover] = useState<Cover | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [batchN, setBatchN] = useState(8);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [stats, setStats] = useState({
    iou: null as number | null, prec: null as number | null,
    rec: null as number | null, flood: null as number | null, perm: 0,
  });

  const rootRef = useRef<HTMLDivElement>(null);
  const zoom = useZoomPan();
  const predRef = useRef<HTMLCanvasElement>(null);
  const pred2Ref = useRef<HTMLCanvasElement>(null);
  const agreeRef = useRef<HTMLCanvasElement>(null);
  const permRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    api.floodSamples().then((d) => {
      setRegions(d.regions);
      const first = d.regions["India"] ? "India" : Object.keys(d.regions)[0];
      setRegion(first);
      setChip(d.regions[first]?.[0] ?? "");
    }).catch((e) => setErr(e.message));
  }, []);

  const chips = regions[region] ?? [];
  useEffect(() => { if (chips.length && !chips.includes(chip)) setChip(chips[0]); },
    [region, chips, chip]);

  const run = useCallback(async () => {
    if (!chip) return;
    setBusy(true); setErr("");
    try {
      const d = await api.floodPredict(chip);
      // record it however it was opened - palette, dropdown, arrow keys or shortcut
      window.dispatchEvent(new CustomEvent("chromasar:opened", { detail: chip }));
      const [probImg, labImg, permImg] = await Promise.all([
        loadImage(d.prob),
        d.label ? loadImage(d.label) : Promise.resolve(null),
        d.permanent ? loadImage(d.permanent) : Promise.resolve(null),
      ]);
      const prob = toPixels(probImg);
      const hist = new Array(64).fill(0);
      for (let i = 0; i < probImg.width * probImg.height; i++)
        hist[Math.min(63, prob.data[i * 4] >> 2)]++;
      setData({
        name: chip, prob,
        label: labImg ? toPixels(labImg) : null,
        perm: permImg ? toPixels(permImg) : null,
        w: probImg.width, h: probImg.height,
        vv: d.sar_vv, vh: d.sar_vh, hist, ms: d.ms, pixelM2: d.pixel_m2 ?? null,
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [chip]);

  /* threshold + scoring, entirely client-side => the slider is instant */
  useEffect(() => {
    if (!data) return;
    const { prob, label, perm, w, h } = data;
    const usePerm = excludePerm && perm !== null;
    // Canvases mount/unmount as layers switch, so scoring must NOT depend on any of
    // them existing. Compute into standalone buffers and paint whatever is present.
    // (Regression once shipped: metrics stayed at "-" in compare mode because two of
    // the three refs were null and the effect bailed out early.)
    const pred = new ImageData(w, h), agree = new ImageData(w, h);
    let tp = 0, fp = 0, fn = 0, permWet = 0, floodWet = 0, valid = 0;

    for (let i = 0; i < w * h; i++) {
      const k = i * 4, g = prob.data[k];
      let p = g / 255 > thr;
      const isPerm = usePerm && perm!.data[k] > 127;
      if (p) { if (isPerm) permWet++; else floodWet++; }
      // Permanent water is removed from BOTH prediction and truth. Dropping it from
      // one side only turns every river pixel into a false negative (0.861 -> 0.263).
      if (usePerm && isPerm) p = false;

      if (p) { pred.data[k] = 61; pred.data[k + 1] = 220; pred.data[k + 2] = 255; }
      else {
        const v = g * 0.42;
        pred.data[k] = v; pred.data[k + 1] = v * 1.04; pred.data[k + 2] = v * 1.12;
      }
      pred.data[k + 3] = 255;

      if (label) {
        const L = label.data[k];
        let r = 17, gg = 26, b = 38;
        if (L !== 128 && !(usePerm && isPerm)) {
          valid++;
          const t = L === 255;
          if (p && t) { tp++; r = 62; gg = 224; b = 143; }
          else if (p && !t) { fp++; r = 255; gg = 95; b = 109; }
          else if (!p && t) { fn++; r = 90; gg = 166; b = 255; }
          else { r = 10; gg = 16; b = 24; }
        }
        agree.data[k] = r; agree.data[k + 1] = gg;
        agree.data[k + 2] = b; agree.data[k + 3] = 255;
      }
    }
    predRef.current?.getContext("2d")?.putImageData(pred, 0, 0);
    pred2Ref.current?.getContext("2d")?.putImageData(pred, 0, 0);

    // A guarded paint with no else branch leaves the PREVIOUS scene's pixels on the
    // canvas. Uploads carry no hand labels and no permanent-water layer, so loading one
    // while the Agreement layer is open used to show the last benchmark chip's
    // hit/false-positive/missed map over the new scene - with the legend underneath
    // still naming those colours. Same failure as the black-canvas bug: the bitmap
    // outlived the state that produced it, and nothing errored.
    const ga = agreeRef.current?.getContext("2d");
    if (label) ga?.putImageData(agree, 0, 0);
    else ga?.clearRect(0, 0, w, h);

    if (!perm) permRef.current?.getContext("2d")?.clearRect(0, 0, w, h);
    if (perm) {
      const g2 = permRef.current?.getContext("2d");
      if (g2) {
        const im = new ImageData(w, h);
        for (let i = 0; i < w * h; i++) {
          const on = perm.data[i * 4] > 127, k = i * 4;
          im.data[k] = on ? 90 : 12; im.data[k + 1] = on ? 140 : 18;
          im.data[k + 2] = on ? 230 : 26; im.data[k + 3] = 255;
        }
        g2.putImageData(im, 0, 0);
      }
    }
    setStats({
      iou: label && valid ? tp / Math.max(tp + fp + fn, 1) : null,
      prec: label && valid ? tp / Math.max(tp + fp, 1) : null,
      rec: label && valid ? tp / Math.max(tp + fn, 1) : null,
      // true ground area from the scene's own georeferencing, not a flat 100 m²
      flood: floodWet * ((data.pixelM2 ?? 100) / 1e6),
      perm: permWet * ((data.pixelM2 ?? 100) / 1e6),
    });
  // `layer` is in the deps for a non-obvious reason: <ZoomPan> unmounts while Compare
  // is active (it used to sit invisibly on top and swallow the curtain's pointer
  // events), so switching back to a canvas layer mounts a BRAND NEW, unpainted canvas.
  // Without `layer` here, neither of the other deps has changed, the effect never
  // re-runs, and the layer renders pure black while the data sits fine in state - the
  // pixel probe still reads correct values off `px`, which is what makes it confusing.
  }, [data, thr, excludePerm, layer]);

  /* report follows the operating point, debounced so dragging doesn't spam */
  useEffect(() => {
    if (!data) return;
    const t = setTimeout(() => {
      api.floodReport(data.name, thr, excludePerm).then(setReport).catch(() => {});
    }, 260);
    return () => clearTimeout(t);
  // `layer` is in the deps for a non-obvious reason: <ZoomPan> unmounts while Compare
  // is active (it used to sit invisibly on top and swallow the curtain's pointer
  // events), so switching back to a canvas layer mounts a BRAND NEW, unpainted canvas.
  // Without `layer` here, neither of the other deps has changed, the effect never
  // re-runs, and the layer renders pure black while the data sits fine in state - the
  // pixel probe still reads correct values off `px`, which is what makes it confusing.
  }, [data, thr, excludePerm, layer]);

  const sweep = async () => {
    setBusy(true);
    try { setBatch(await api.floodBatch(region, batchN, thr)); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  const upload = async (f: File) => {
    setBusy(true); setErr("");
    try {
      const d = await api.floodUpload(f);
      const probImg = await loadImage(d.prob);
      const prob = toPixels(probImg);
      const hist = new Array(64).fill(0);
      for (let i = 0; i < probImg.width * probImg.height; i++)
        hist[Math.min(63, prob.data[i * 4] >> 2)]++;
      setData({
        name: f.name, prob, label: null, perm: null,
        w: probImg.width, h: probImg.height,
        vv: d.sar_vv, vh: "", hist, ms: 0,
        pixelM2: (d as { pixel_m2?: number }).pixel_m2 ?? null,
      });
      setReport(null);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  const dl = (url: string, name: string) => {
    const a = document.createElement("a");
    a.href = url; a.download = name; a.click();
  };

  /* palette + keyboard both dispatch these, so there is one code path per action */
  useEffect(() => {
    const onScene = (e: Event) => setChip((e as CustomEvent).detail as string);
    const onRun = () => run();
    const onPerm = () => setExcludePerm((v) => !v);
    const onSweep = () => sweep();
    window.addEventListener("chromasar:scene", onScene);
    window.addEventListener("chromasar:run", onRun);
    window.addEventListener("chromasar:perm", onPerm);
    window.addEventListener("chromasar:sweep", onSweep);
    return () => {
      window.removeEventListener("chromasar:scene", onScene);
      window.removeEventListener("chromasar:run", onRun);
      window.removeEventListener("chromasar:perm", onPerm);
      window.removeEventListener("chromasar:sweep", onSweep);
    };
  });

  /* Surface cover comes from the co-registered Sentinel-2 chip, so it depends only on

     which scene is selected - not on the threshold or the model run. */

  useEffect(() => {

    if (!chip) return;

    let live = true;

    setCover(null);

    api.sceneCover(chip).then((c) => { if (live) setCover(c); }).catch(() => {});

    return () => { live = false; };

  }, [chip]);


  /* keyboard - only while this view is the one on screen */
  const step = (d: number) => {
    const i = chips.indexOf(chip);
    setChip(chips[Math.max(0, Math.min(chips.length - 1, i + d))]);
  };
  useHotkeys(rootRef, {
    r: (e) => { e.preventDefault(); run(); },
    p: () => setExcludePerm((v) => !v),
    b: () => sweep(),
    arrowright: () => step(1),
    arrowleft: () => step(-1),
  });

  const canvasStyle = { width: "100%", height: "100%", objectFit: "contain" as const,
                        imageRendering: "pixelated" as const, display: "block" };

  return (
    <div className="layout" ref={rootRef}>
      <aside>
        <div className="card">
          <h3>Scene</h3>
          <div className="row2">
            <div>
              <label htmlFor="region">Region</label>
              <select id="region" value={region} onChange={(e) => setRegion(e.target.value)}>
                {Object.entries(regions).map(([r, list]) =>
                  <option key={r} value={r}>{r} · {list.length}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="chip">Chip</label>
              <select id="chip" value={chip} onChange={(e) => setChip(e.target.value)}>
                {chips.map((c) => <option key={c} value={c}>{c.replace(region + "_", "")}</option>)}
              </select>
            </div>
          </div>
          <button className="go" onClick={run} disabled={busy || !chip}>
            {busy ? <><span className="spin" />running</> : <>Run detection <kbd>R</kbd></>}
          </button>
          <Drop label="or drop your own Sentinel-1 GeoTIFF" accept=".tif,.tiff"
            onFile={upload} disabled={busy} />
        </div>

        <div className="card">
          <h3>Decision</h3>
          <label>Water probability <b>{thr.toFixed(2)}</b></label>
          <input type="range" min={1} max={99} value={Math.round(thr * 100)}
            style={{ ["--pct" as string]: `${thr * 100}%` }}
            onChange={(e) => setThr(+e.target.value / 100)} />
          <Histogram counts={data?.hist ?? []} cut={thr} lo="#24384d" hi="#3ddcff" />
          <label className="switch">
            <span>Exclude permanent water</span>
            <input type="checkbox" checked={excludePerm}
              onChange={(e) => setExcludePerm(e.target.checked)} />
          </label>
        </div>

        <details className="card">
          <summary><h3 style={{ margin: 0 }}>Advanced</h3></summary>
          <label>Region sweep size <b>{batchN}</b></label>
          <input type="range" min={2} max={20} value={batchN}
            style={{ ["--pct" as string]: `${((batchN - 2) / 18) * 100}%` }}
            onChange={(e) => setBatchN(+e.target.value)} />
          <button className="go ghost" onClick={sweep} disabled={busy}>
            Sweep region <kbd>B</kbd>
          </button>
          {batch && (
            <>
              <table className="batch">
                <tbody>
                  <tr><th>scene</th><th>flood km²</th><th>IoU</th></tr>
                  {batch.worst.map((r) => (
                    <tr key={r.scene} onClick={() => setChip(r.scene)}>
                      <td>{r.scene.replace(batch.region + "_", "")}</td>
                      <td>{r.flood_km2.toFixed(2)}</td>
                      <td>{r.iou !== undefined ? r.iou.toFixed(3) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="note tiny">
                <b>{batch.chips}</b> chips · <b>{batch.flood_km2.toFixed(1)} km²</b> flood
                of {batch.water_km2.toFixed(1)} km² water
                {batch.mean_iou !== null && <> · mean IoU {batch.mean_iou.toFixed(3)}</>}
                {" "}· {(batch.ms / 1000).toFixed(1)} s
              </div>
            </>
          )}
        </details>

        <div className="card">
          <h3>Export</h3>
          <div className="exports">
            <button className="mini wide" disabled={!chip}
              onClick={() => dl(api.exportUrl(chip, thr, excludePerm, "mask"),
                               `chromasar_${chip}_mask.tif`)}>
              Flood mask · GeoTIFF
            </button>
            <button className="mini wide" disabled={!chip}
              onClick={() => dl(api.exportUrl(chip, thr, excludePerm, "probability"),
                               `chromasar_${chip}_prob.tif`)}>
              Probability · GeoTIFF
            </button>
            <button className="mini wide" disabled={!report}
              onClick={() => {
                const b = new Blob([JSON.stringify(report, null, 2)],
                                   { type: "application/json" });
                dl(URL.createObjectURL(b), `chromasar_${chip}.json`);
              }}>
              Report · JSON
            </button>
          </div>
          <div className="note tiny">GeoTIFFs carry the source georeferencing, so they
            overlay correctly in QGIS.</div>
        </div>
      </aside>

      <div>
        {err && <div className="warn"><div>{err}</div></div>}

        <div className="metrics">
          <Metric tone="lead" value={stats.flood} label="Flood extent" digits={2} suffix=" km²" />
          <Metric value={stats.iou} label="IoU" />
          <Metric value={stats.prec} label="Precision" />
          <Metric value={stats.rec} label="Recall" />
        </div>

        <figure className="hero">
          <figcaption>
            <div className="layers">
              {LAYERS.map(([id, lbl]) => (
                <button key={id} className={layer === id ? "active" : ""}
                  onClick={() => setLayer(id)}>{lbl}</button>
              ))}
            </div>
            <span style={{ marginLeft: "auto", color: "var(--ink-4)", fontSize: 10.5 }}>
              {layer === "compare" ? "drag the divider"
                : "scroll to zoom · drag to pan · double-click to reset"}
            </span>
          </figcaption>

          <div className={`stage ${busy ? "busy" : ""}`} ref={zoom.ref}
            style={data ? { ["--ar" as string]: `${data.w} / ${data.h}` } : undefined}>
            {!data && <div className="empty">Pick a scene and press Run detection</div>}
            {data && (
              <div className={`pane ${layer === "compare" ? "on" : ""}`}>
                <Compare zoom={zoom} leftLabel="SAR" rightLabel="detected"
                  base={<img src={data.vv} alt="SAR VV" />}
                  top={<canvas ref={predRef} width={data.w} height={data.h} />} />
              </div>
            )}
            {data && (
              <ZoomPan zoom={zoom} active={layer !== "compare"}>
                <div className={`pane ${layer === "pred" ? "on" : ""}`}>
                  <canvas ref={pred2Ref} width={data.w} height={data.h} style={canvasStyle} />
                </div>
                <div className={`pane ${layer === "agree" ? "on" : ""}`}>
                  <canvas ref={agreeRef} width={data.w} height={data.h} style={canvasStyle} />
                  {!data.label && (
                    <div className="empty">no hand labels for this input — agreement
                      cannot be shown</div>
                  )}
                </div>
                <div className={`pane ${layer === "vv" ? "on" : ""}`}>
                  <img src={data.vv} alt="VV" style={canvasStyle} />
                </div>
                <div className={`pane ${layer === "vh" ? "on" : ""}`}>
                  {data.vh ? <img src={data.vh} alt="VH" style={canvasStyle} />
                           : <div className="empty">no VH for this input</div>}
                </div>
                <div className={`pane ${layer === "perm" ? "on" : ""}`}>
                  <canvas ref={permRef} width={data.w} height={data.h} style={canvasStyle} />
                
                  {!data.perm && (
                    <div className="empty">no permanent-water reference for this input</div>
                  )}
                </div>
              </ZoomPan>
            )}
            {data && <ZoomControls zoom={zoom} />}
          </div>

          <div className="barfoot">
            {layer === "agree" && data?.label && (
              <div className="legend">
                <span><i style={{ background: "#3ee08f" }} />hit</span>
                <span><i style={{ background: "#ff5f6d" }} />false positive</span>
                <span><i style={{ background: "#5aa6ff" }} />missed</span>
                <span><i style={{ background: "#1b2b3d" }} />unlabelled</span>
              </div>
            )}
            <span className="spacer" />
            <span className="chip">permanent {stats.perm.toFixed(2)} km²</span>
            <span className="chip">{data ? `${data.ms} ms` : "— ms"}</span>
          </div>
        </figure>

        {(cover || report) && (
          <CoverPanel cover={cover} metrics={report?.metrics} />
        )}

        {report && (
          <details className="card report-card" open>
            <summary>
              <h3 style={{ margin: 0 }}>Situation report</h3>
              <span className="spacer" />
              <span className="chip">{report.severity}</span>
            </summary>
            <div className={`alert ${report.alert ? "on" : "off"}`}>
              <span className="badge">{report.alert ? "alert" : "no alert"}</span>
              {report.alert
                ? `Flood extent ${report.metrics.flood_pct_of_scene.toFixed(1)}% of scene · confidence sufficient to act`
                : report.severity === "negligible"
                  ? "Below alert threshold"
                  : "Extent significant but too much of the scene is low-confidence — routed for analyst review"}
            </div>
            <ul className="report">
              {report.narrative.map((l, i) => <li key={i}>{l}</li>)}
            </ul>
          </details>
        )}

        <details className="card">
          <summary><h3 style={{ margin: 0 }}>Why this works</h3></summary>
          <div className="note">
            Water is a <b>specular reflector</b> — it bounces the radar pulse away from
            the satellite, so open water returns almost no energy and appears near-black.
            The exception is floodwater under vegetation, which double-bounces off trunks
            and returns <b>bright</b>: the case a pure threshold misses and a learned
            model catches. Probabilities are temperature-calibrated, and permanent water
            from the JRC layer is subtracted so the reported number is <b>new</b> water,
            not rivers that were always there.
          </div>
        </details>
      </div>
    </div>
  );
}
