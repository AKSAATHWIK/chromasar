"use client";
import type { Cover, ReportMetrics } from "@/lib/api";

/** Colours are the data legend, not decoration - water reads as water, bare as soil. */
const HUE: Record<string, string> = {
  water: "#3ec9ff", dense: "#2f9e63", moderate: "#5fc97f",
  sparse: "#c8b45c", bare: "#b8763f",
};

/** Where the scene is, and what is on the ground.
 *
 * The two halves have DIFFERENT provenance and the panel says so, because conflating
 * them would be the dishonest move: the location is read from the GeoTIFF's own
 * georeferencing tags and is exact, whereas the cover fractions are measured from the
 * co-registered Sentinel-2 optical chip - not from the radar.
 *
 * We tested whether C-band SAR could produce this breakdown on its own. It could not:
 * built-up scored below chance against bare soil, and per-scene area errors for bare
 * and sparse classes were as large as the quantities being reported. Rather than print
 * five confident numbers, the app reports what the optical instrument actually measured
 * and names the class it refuses to estimate.
 */
export function CoverPanel({ cover, metrics }: {
  cover: Cover | null; metrics?: ReportMetrics;
}) {
  const place = cover?.place ?? metrics?.place ?? null;
  const coords = cover?.coords ?? metrics?.coords ?? null;

  return (
    <div className="card">
      <h3>Location &amp; surface cover</h3>

      <div className="place">
        <b>{place ?? "Location unknown"}</b>
        {coords && <span>{coords}</span>}
        {metrics?.pixel_m2 && (
          <span>· {metrics.pixel_m2.toFixed(1)} m² per pixel</span>
        )}
      </div>

      {!cover ? (
        <div className="note tiny">Measuring surface cover…</div>
      ) : !cover.usable ? (
        <div className="note tiny">
          Surface cover unavailable — <b>{cover.reason}</b>. The optical chip for this
          scene is {(100 * cover.cloud_fraction).toFixed(0)}% cloud, and cover is
          measured optically, so no estimate is reported rather than a guessed one.
        </div>
      ) : (
        <>
          <div className="cover">
            <div className="coverbar" role="img"
              aria-label={cover.classes.map((c) => `${c.label} ${c.pct}%`).join(", ")}>
              {cover.classes.map((c) => (
                <i key={c.key} style={{ width: `${c.pct}%`, background: HUE[c.key] }} />
              ))}
            </div>
            {cover.classes.map((c) => (
              <div className="coverrow" key={c.key}>
                <i className="sw" style={{ background: HUE[c.key] }} />
                <span className="nm">{c.label}</span>
                <span className="nt">{c.note}</span>
                <span className="pc">{c.pct.toFixed(1)}%</span>
              </div>
            ))}
          </div>

          <div className="note tiny mt">
            Measured from the co-registered <b>Sentinel-2 optical</b> chip, over the{" "}
            {(100 * (1 - cover.cloud_fraction)).toFixed(0)}% of it that is cloud-free —
            cloud is excluded from the denominator, not spread across the classes.
            <br />
            <b>Built-up area is not reported.</b> We measured it: at C-band it is not
            separable from bare soil (AUC 0.483, below chance), and the optical reference
            label for it assigns 26% of rural Pakistani flood plain to buildings. A
            number we cannot score is worse than no number.
          </div>
        </>
      )}
    </div>
  );
}
