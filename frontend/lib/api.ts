/** Typed client for the FastAPI backend.
 *
 * Next rewrites /api/* to 127.0.0.1:8000, so the browser sees one origin and there is
 * no CORS surface at all. The Python service is unchanged.
 */

export type Status = {
  device: string;
  flood_model: boolean;
  color_model: boolean;
  temperature: number;
  flood_chips: number;
  sar_pairs: number;
};

export type FloodPredict = {
  name: string;
  temperature: number;
  sar_vv: string;
  sar_vh: string;
  prob: string;
  label?: string;
  permanent?: string;
  permanent_frac?: number;
  water_frac?: number;
  ms: number;
  size: [number, number];
  /** true ground area of one pixel, from the scene's own georeferencing */
  pixel_m2: number;
};

export type ReportMetrics = {
  scene: string; region: string; threshold: number;
  water_km2: number; permanent_km2: number; flood_km2: number;
  scene_km2: number; flood_pct_of_scene: number;
  uncertain_fraction: number; mean_probability: number;
  iou?: number; precision?: number; recall?: number;
  place?: string | null; country?: string | null; continent?: string | null;
  coords?: string | null; pixel_m2?: number | null;
};

export type CoverClass = { key: string; label: string; pct: number; note: string };
export type Cover = {
  scene: string; usable: boolean; reason?: string;
  place: string | null; country: string | null; continent: string | null;
  coords: string | null;
  source?: string; cloud_fraction: number; median_ndvi?: number | null;
  classes: CoverClass[]; not_reported?: string[]; caveat?: string;
};

export type Report = {
  metrics: ReportMetrics;
  narrative: string[];
  alert: boolean;
  severity: "negligible" | "localised" | "significant" | "severe";
};

export type Batch = {
  region: string; chips: number;
  flood_km2: number; water_km2: number; permanent_km2: number;
  mean_iou: number | null;
  worst: ReportMetrics[];
  ms: number;
};

export type ColorPredict = {
  name: string; sar: string; color: string; confidence: string;
  truth?: string; passes: number; ms: number; mean_confidence: number;
  /** only present for uploads - tells you how the file was interpreted */
  source?: string;
};

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) {
    const body = await r.json().catch(() => ({} as { detail?: string }));
    throw new Error(body.detail ?? `${r.status} ${r.statusText}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  status: () => get<Status>("/api/status"),
  floodSamples: (limit = 40) =>
    get<{ regions: Record<string, string[]>; total: number }>(
      `/api/flood/samples?limit=${limit}`),
  floodPredict: (name: string) =>
    get<FloodPredict>(`/api/flood/predict?name=${encodeURIComponent(name)}`),
  floodReport: (name: string, thr: number, excludePermanent: boolean) =>
    get<Report>(
      `/api/flood/report?name=${encodeURIComponent(name)}&thr=${thr}` +
      `&exclude_permanent=${excludePermanent}`),
  floodBatch: (region: string, limit: number, thr: number) =>
    get<Batch>(
      `/api/flood/batch?region=${encodeURIComponent(region)}&limit=${limit}&thr=${thr}`),
  exportUrl: (name: string, thr: number, excludePermanent: boolean, kind: string) =>
    `/api/flood/export?name=${encodeURIComponent(name)}&thr=${thr}` +
    `&exclude_permanent=${excludePermanent}&kind=${kind}`,
  sceneCover: (name: string) =>
    get<Cover>(`/api/scene/cover?name=${encodeURIComponent(name)}`),
  colorSamples: () =>
    get<{ samples: string[]; total: number }>("/api/color/samples"),
  colorPredict: (name: string, passes: number) =>
    get<ColorPredict>(
      `/api/color/predict?name=${encodeURIComponent(name)}&passes=${passes}`),
  async colorUpload(file: File, passes: number) {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`/api/color/upload?passes=${passes}`,
      { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail ?? "upload failed");
    return d as ColorPredict;
  },
  async floodUpload(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/flood/upload", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail ?? "upload failed");
    return d as { name: string; sar_vv: string; prob: string; size: [number, number] };
  },
};

/* ---------------- imaging helpers ---------------- */
export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((res, rej) => {
    const i = new Image();
    i.onload = () => res(i);
    i.onerror = () => rej(new Error("image decode failed"));
    i.src = src;
  });
}

export function toPixels(img: HTMLImageElement): ImageData {
  const c = document.createElement("canvas");
  c.width = img.width;
  c.height = img.height;
  const x = c.getContext("2d", { willReadFrequently: true })!;
  x.drawImage(img, 0, 0);
  return x.getImageData(0, 0, c.width, c.height);
}

/** Save an ImageData buffer as a PNG. Used for colorization exports, which are produced
 *  in the browser (gating is applied client-side, so the server never sees the pixels
 *  the user is actually looking at - exporting the server copy would ship a DIFFERENT
 *  image from the one on screen). */
export function downloadImageData(px: ImageData, filename: string) {
  const c = document.createElement("canvas");
  c.width = px.width; c.height = px.height;
  c.getContext("2d")!.putImageData(px, 0, 0);
  c.toBlob((b) => {
    if (!b) return;
    const u = URL.createObjectURL(b);
    const a = document.createElement("a");
    a.href = u; a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(u), 1000);
  }, "image/png");
}

/** Nominal fallback ONLY. Sen1Floods11 rasters are in a geographic CRS, so a degree of
 *  longitude shrinks as cos(latitude) and a "10 m" pixel is 89 m² at India's latitude,
 *  78 m² at Spain's. Using this constant to report area made the metric tile read
 *  15.06 km² while the report card beside it said 13.42 for the SAME scene. Always
 *  prefer `pixel_m2` from the API; this is what to use when a file carries no
 *  georeferencing at all. */
export const PIXEL_KM2 = (10 * 10) / 1e6;
