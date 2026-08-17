"use client";
import { useEffect, type RefObject } from "react";

/** Keyboard shortcuts scoped to a view that is actually on screen.
 *
 * Every view mounts all the time - tabs are switched with `display:none`, not by
 * unmounting - so a plain window listener in FloodView kept firing while you were on
 * the Colorization tab. Pressing R there silently re-ran flood detection on a scene you
 * could not see. `offsetParent === null` is exactly the "display:none somewhere above
 * me" test, so a hidden view simply ignores the key.
 *
 * Typing targets and any open dialog are excluded, so shortcuts never steal characters
 * from the command palette or a text field. */
export function useHotkeys(
  root: RefObject<HTMLElement | null>,
  map: Record<string, (e: KeyboardEvent) => void>,
) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (["INPUT", "SELECT", "TEXTAREA"].includes(t.tagName) || t.isContentEditable))
        return;
      if (document.querySelector(".palette, .keyshelp")) return;
      if (!root.current || root.current.offsetParent === null) return;
      const fn = map[e.key.toLowerCase()];
      if (fn) fn(e);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });
}
