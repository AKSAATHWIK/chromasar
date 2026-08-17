"use client";
import { useEffect } from "react";

const GROUPS: [string, [string, string][]][] = [
  ["Navigation", [
    ["1–4", "Switch workspace"],
    ["Ctrl K", "Search scenes and actions"],
    ["?", "This list"],
    ["Esc", "Close"],
  ]],
  ["Flood mapping", [
    ["R", "Run detection on the current scene"],
    ["P", "Toggle permanent-water exclusion"],
    ["B", "Sweep the whole region"],
    ["← →", "Previous / next scene"],
  ]],
  ["Colorization", [
    ["R", "Colorize the current tile"],
    ["[ ]", "Lower / raise the confidence gate"],
    ["← →", "Cycle layers"],
  ]],
];

/** Shortcut reference. Only reachable with a physical keyboard, so it is hidden on
 *  touch widths rather than shown as a list of keys nobody can press. */
export function Keys({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  return (
    <div className="keyshelp" onClick={onClose} role="dialog" aria-modal="true"
      aria-label="Keyboard shortcuts">
      <div className="box" onClick={(e) => e.stopPropagation()}>
        <header>
          <h3>Keyboard shortcuts</h3>
          <button onClick={onClose} aria-label="close">×</button>
        </header>
        {GROUPS.map(([grp, rows]) => (
          <div key={grp}>
            <div className="grp">{grp}</div>
            {rows.map(([k, d]) => (
              <div className="krow" key={k + d}>
                <span>{d}</span>
                {k.split(" ").map((part, i) => <kbd key={i}>{part}</kbd>)}
              </div>
            ))}
          </div>
        ))}
        <div className="grp" style={{ paddingBottom: 14 }}>
          Shortcuts apply to the workspace you are looking at.
        </div>
      </div>
    </div>
  );
}
