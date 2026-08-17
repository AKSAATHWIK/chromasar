import type { ReactNode } from "react";

/** Shared navigation metadata. Lives here rather than in a page so the shell layout and
 *  every route agree on the same four workspaces, their copy and their icons. */
export const TABS = [
  ["flood", "Flood mapping", "Detect and quantify inundation from a single SAR scene"],
  ["change", "Change detection", "Compare two acquisitions of the same footprint"],
  ["color", "Colorization", "Render SAR as optical-like imagery, with confidence"],
  ["method", "Method", "Benchmarks, calibration and how the numbers were produced"],
] as const;

/** Which corpus each workspace actually reads from. */
export const DATASET: Record<string, string> = {
  flood: "Sen1Floods11", change: "Sentinel-1 GRD", color: "SEN1-2", method: "Sen1Floods11",
};

export const ICON: Record<string, ReactNode> = {
  flood: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 15c2 0 2-1.6 4-1.6S8 15 10 15s2-1.6 4-1.6 2 1.6 4 1.6 2-1.6 4-1.6" />
      <path d="M2 20c2 0 2-1.6 4-1.6S8 20 10 20s2-1.6 4-1.6 2 1.6 4 1.6 2-1.6 4-1.6" />
      <path d="M12 3v7M9 6l3-3 3 3" />
    </svg>
  ),
  change: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7h13l-3.5-3.5M21 17H8l3.5 3.5" />
      <circle cx="18.5" cy="7" r="2.2" /><circle cx="5.5" cy="17" r="2.2" />
    </svg>
  ),
  color: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" stroke="none" opacity=".55" />
    </svg>
  ),
  method: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 7.5v.6" />
    </svg>
  ),
};
