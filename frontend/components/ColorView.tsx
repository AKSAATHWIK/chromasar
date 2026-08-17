"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, downloadImageData, loadImage, toPixels, type ColorPredict } from "@/lib/api";
import { useHotkeys } from "@/lib/hotkeys";
import { Metric } from "./Metric";
import { Histogram } from "./Histogram";
import { Compare } from "./Compare";
import { ZoomPan, ZoomControls } from "./ZoomPan";
import { useZoomPan } from "@/lib/useZoomPan";
import { Drop } from "./Drop";

const LAYERS = [
  ["compare", "Compare"], ["out", "Colorized"], ["truth", "Ground truth"],
  ["conf", "Confidence"],
] as const;
type Layer = (typeof LAYERS)[number][0];

/** filename without its extension, safe for a download name */
const stem = (n?: string) => (n ?? "tile").replace(/\.[^.]+$/, "").replace(/[^\w.-]+/g, "_");

export function ColorView({ enabled }: { enabled: boolean }) {
  const [samples, setSamples] = useState<string[]>([]);
  const [tile, setTile] = useState("");
  const [passes, setPasses] = useState(10);
  const [gate, setGate] = useState(0);
  const [layer, setLayer] = useState<Layer>("compare");
  const [raw, setRaw] = useState<ColorPredict | null>(null);
  const [px, setPx] = useState<{
    color: ImageData; conf: ImageData; truth: ImageData | null;
    w: number; h: number; hist: number[];
  } | null>(null);
  const [gated, setGated] = useState<number | null>(null);
  const [psnr, setPsnr] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [src, setSrc] = useState<string | null>(null);
  /** last gated frame, kept so export ships exactly what is on screen */
  const [frame, setFrame] = useState<ImageData | null>(null);
  const [probe, setProbe] = useState<{ x: number; y: number; c: number } | null>(null);

  const rootRef = useRef<HTMLDivElement>(null);
  const zoom = useZoomPan();
  const outRef = useRef<HTMLCanvasElement>(null);
  const out2Ref = useRef<HTMLCanvasElement>(null);
  const confRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    api.colorSamples().then((d) => {
      setSamples(d.samples);
      setTile(d.samples[0] ?? "");
    }).catch(() => {});
  }, []);

  /** Decode a prediction into pixel buffers. Identical for benchmark tiles and for
   *  uploads - the upload path is the SAME generator on the SAME single channel, so
   *  there is no second code path that could quietly behave differently. */
  const ingest = useCallback(async (d: ColorPredict) => {
    setRaw(d);
    setSrc(d.source ?? null);
    const [c, cf, t] = await Promise.all([
      loadImage(d.color), loadImage(d.confidence),
      d.truth ? loadImage(d.truth) : Promise.resolve(null),
    ]);
    const conf = toPixels(cf);
    const hist = new Array(64).fill(0);
    for (let i = 0; i < c.width * c.height; i++)
      hist[Math.min(63, conf.data[i * 4] >> 2)]++;
    setPx({
      color: toPixels(c), conf, truth: t ? toPixels(t) : null,
      w: c.width, h: c.height, hist,
    });
    if (!d.truth) setLayer((l) => (l === "truth" ? "compare" : l));
  }, []);

  const run = useCallback(async () => {
    if (!tile) return;
    setBusy(true); setErr("");
    try {
      await ingest(await api.colorPredict(tile, passes));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [tile, passes, ingest]);

  const upload = useCallback(async (f: File) => {
    setBusy(true); setErr("");
    try {
      await ingest(await api.colorUpload(f, passes));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [passes, ingest]);

  /* Gating happens here, on canvas, so the slider re-renders instantly. */
  useEffect(() => {
    if (!px) return;
    const { color, conf, truth, w, h } = px;
    // independent of which canvases are currently mounted - see FloodView
    const out = new ImageData(w, h);
    const cmap = new ImageData(w, h);
    let g = 0, se = 0, n = 0;
    for (let i = 0; i < w * h; i++) {
      const k = i * 4, c = conf.data[k] / 255;
      if (c < gate) {
        g++;
        out.data[k] = out.data[k + 1] = out.data[k + 2] = 84;
      } else {
        out.data[k] = color.data[k];
        out.data[k + 1] = color.data[k + 1];
        out.data[k + 2] = color.data[k + 2];
        if (truth) {
          for (let ch = 0; ch < 3; ch++) {
            const d0 = (color.data[k + ch] - truth.data[k + ch]) / 255;
            se += d0 * d0; n++;
          }
        }
      }
      out.data[k + 3] = 255;
      cmap.data[k] = Math.round(255 * (1 - c));
      cmap.data[k + 1] = Math.round(215 * c);
      cmap.data[k + 2] = Math.round(70 + 40 * c);
      cmap.data[k + 3] = 255;
    }
    outRef.current?.getContext("2d")?.putImageData(out, 0, 0);
    out2Ref.current?.getContext("2d")?.putImageData(out, 0, 0);
    confRef.current?.getContext("2d")?.putImageData(cmap, 0, 0);
    setFrame(out);
    setGated((100 * g) / (w * h));
    setPsnr(truth && n ? 10 * Math.log10(1 / (se / n)) : null);
  // `layer` is in the deps for a non-obvious reason: <ZoomPan> unmounts while Compare
  // is active (it used to sit invisibly on top and swallow the curtain's pointer
  // events), so switching back to a canvas layer mounts a BRAND NEW, unpainted canvas.
  // Without `layer` here, neither of the other deps has changed, the effect never
  // re-runs, and the layer renders pure black while the data sits fine in state - the
  // pixel probe still reads correct values off `px`, which is what makes it confusing.
  }, [px, gate, layer]);

  const cs = {
    width: "100%", height: "100%", objectFit: "contain" as const,
    imageRendering: "pixelated" as const, display: "block",
  };

  useHotkeys(rootRef, {
    r: (e) => { e.preventDefault(); run(); },
    "[": () => setGate((g) => Math.max(0, +(g - 0.05).toFixed(2))),
    "]": () => setGate((g) => Math.min(0.99, +(g + 0.05).toFixed(2))),
    arrowright: () => setLayer((l) => LAYERS[(LAYERS.findIndex(([i]) => i === l) + 1)
      % LAYERS.length][0]),
    arrowleft: () => setLayer((l) => LAYERS[(LAYERS.findIndex(([i]) => i === l)
      + LAYERS.length - 1) % LAYERS.length][0]),
  });

  return (
    <div className="layout" ref={rootRef}>
      <aside>
        <div className="card">
          <h3>SAR tile</h3>
          <label htmlFor="ctile">Tile</label>
          <select id="ctile" value={tile} onChange={(e) => setTile(e.target.value)}>
            {samples.map((s) => (
              <option key={s} value={s}>{s.replace(".png", "").slice(-24)}</option>
            ))}
          </select>
          <label>MC-dropout passes <b>{passes}</b></label>
          <input type="range" min={2} max={24} value={passes}
            style={{ ["--pct" as string]: `${((passes - 2) / 22) * 100}%` }}
            onChange={(e) => setPasses(+e.target.value)} />
          <button className="go" onClick={run} disabled={!enabled || busy || !tile}>
            {busy ? <><span className="spin" />sampling</> : "Colorize"}
          </button>

          <div className="sep-h" />
          <label>Your own SAR</label>
          <Drop label="drop or click - 1-band SAR GeoTIFF or grayscale PNG"
            onFile={upload} disabled={!enabled || busy} />
          <div className="note tiny">
            Single-channel only. A dB-scaled GeoTIFF is mapped from -30..0 dB; an 8-bit
            image is taken as already stretched. The colour comes from the radar you
            supply - nothing else is consulted.
          </div>
        </div>

        <div className="card">
          <h3>Confidence gate</h3>
          <label>Refuse below <b>{gate.toFixed(2)}</b></label>
          <input type="range" min={0} max={99} value={Math.round(gate * 100)}
            style={{ ["--pct" as string]: `${gate * 100}%` }}
            onChange={(e) => setGate(+e.target.value / 100)} />
          <Histogram counts={px?.hist ?? []} cut={gate} lo="#4a2418" hi="#3ee08f" />
          <div className="note tiny">
            Pixels below the gate return neutral grey —
            <b> insufficient evidence</b> rather than a confident guess.
          </div>
        </div>

        <div className="card">
          <h3>Export</h3>
          <div className="row2">
            <button className="mini" disabled={!frame}
              onClick={() => frame && downloadImageData(
                frame, `${stem(raw?.name)}_colorized.png`)}>
              Colorized PNG
            </button>
            <button className="mini" disabled={!px}
              onClick={() => px && downloadImageData(
                px.conf, `${stem(raw?.name)}_confidence.png`)}>
              Confidence PNG
            </button>
          </div>
          <div className="note tiny">
            The colorized export is the <b>gated</b> frame you are looking at, not the
            raw server output — what you see is what you get.
          </div>
        </div>
      </aside>

      <div>
        {!enabled && <div className="warn"><div>Colorization model not loaded.</div></div>}
        {err && <div className="warn"><div>{err}</div></div>}

        {src && (
          <div className="note tiny mb">
            Read <b>{raw?.name}</b> as <b>{src}</b>
            {px && <> · {px.w}&times;{px.h} px</>}
          </div>
        )}

        <div className="metrics">
          <Metric tone="lead" value={raw?.mean_confidence ?? null} label="Mean confidence" />
          <Metric value={gated} label="Gated out" digits={1} suffix="%" />
          <Metric value={psnr} label="PSNR vs truth" digits={2} suffix=" dB" />
          <Metric value={raw?.ms ?? null} label="Inference" digits={0} suffix=" ms" />
        </div>

        <figure className="hero">
          <figcaption>
            <div className="layers">
              {LAYERS.map(([id, lbl]) => (
                <button key={id} className={layer === id ? "active" : ""}
                  onClick={() => setLayer(id)}>{lbl}</button>
              ))}
            </div>
          </figcaption>

          <div className={`stage ${busy ? "busy" : ""}`} ref={zoom.ref}
            style={px ? { ["--ar" as string]: `${px.w} / ${px.h}` } : undefined}>
            {!px && <div className="empty">Pick a tile and press Colorize</div>}
            {px && raw && (
              <div className={`pane ${layer === "compare" ? "on" : ""}`}>
                <Compare leftLabel="SAR input" rightLabel="colorized" zoom={zoom}
                  base={<img src={raw.sar} alt="SAR input" />}
                  top={<canvas ref={outRef} width={px.w} height={px.h} />} />
              </div>
            )}
            {px && raw && (
              <ZoomPan zoom={zoom} active={layer !== "compare"}>
                <div className={`pane ${layer === "out" ? "on" : ""}`}>
                  <canvas ref={out2Ref} width={px.w} height={px.h} style={cs} />
                </div>
                <div className={`pane ${layer === "truth" ? "on" : ""}`}>
                  {raw.truth
                    ? <img src={raw.truth} alt="ground truth" style={cs} />
                    : <div className="empty">no ground truth for this tile</div>}
                </div>
                <div className={`pane ${layer === "conf" ? "on" : ""}`}>
                  <canvas ref={confRef} width={px.w} height={px.h} style={cs}
                    onMouseLeave={() => setProbe(null)}
                    onMouseMove={(e) => {
                      const r = e.currentTarget.getBoundingClientRect();
                      // objectFit:contain letterboxes the canvas, so the drawn box is
                      // not the element box - map through the real scale or the readout
                      // is offset by the bars.
                      const sc = Math.min(r.width / px.w, r.height / px.h);
                      const dw = px.w * sc, dh = px.h * sc;
                      const x = Math.floor((e.clientX - r.left - (r.width - dw) / 2) / sc);
                      const y = Math.floor((e.clientY - r.top - (r.height - dh) / 2) / sc);
                      if (x < 0 || y < 0 || x >= px.w || y >= px.h) { setProbe(null); return; }
                      setProbe({ x, y, c: px.conf.data[(y * px.w + x) * 4] / 255 });
                    }} />
                  {probe && (
                    <div className="probe">
                      <b>{probe.c.toFixed(3)}</b> confidence
                      <span> · {probe.x},{probe.y}</span>
                      <span> · {probe.c < gate ? "gated out" : "shown"}</span>
                    </div>
                  )}
                </div>
              </ZoomPan>
            )}
            {px && <ZoomControls zoom={zoom} />}
          </div>
        </figure>

        <details className="card">
          <summary><h3 style={{ margin: 0 }}>Honest limitations</h3></summary>
          <div className="note">
            <b>Radar does not measure colour.</b> Part of this output is inference from
            texture and polarisation; part is the model guessing from learned priors.
            Running the generator repeatedly with dropout live gives many plausible
            answers — agreement means evidence, divergence means invention.
            <br /><br />
            <b>This model was retrained to remove blur.</b> The first version was five
            times smoother than the real optical, because an L1-dominated loss is
            minimised by the conditional mean of every plausible colour. Adding a
            gradient-difference term and raising the adversarial weight lifted gradient
            energy from 0.21 to 0.78 of the ground truth and saturation from 45% to 102%.
            It cost pixel fidelity: perceptual distance rose 2.03 → 2.75. Spatial variance
            is 51% of reality — better, not solved.
            <br /><br />
            <b>More MC passes means less texture.</b> Averaging stochastic passes smooths
            them: sharpness is 0.53 at 2 passes and 0.43 at 20. The slider trades a better
            uncertainty estimate against detail, and we would rather show you that dial
            than hide it.
          </div>
        </details>
      </div>
    </div>
  );
}
