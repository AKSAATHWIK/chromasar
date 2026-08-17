"use client";
import { useEffect, useMemo, useRef, useState } from "react";

export type Command = {
  id: string;
  label: string;
  group: string;
  hint?: string;
  run: () => void;
};

/** ⌘K / Ctrl-K command palette.
 *
 * Present because it is how anyone who lives in tools expects to navigate: type a
 * scene name, hit enter, done — rather than hunting two dropdowns. It also gives
 * every action a discoverable name, which is worth more than a second toolbar. */
export function Palette({ commands }: { commands: Command[] }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
        setQ(""); setSel(0);
      } else if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 20); }, [open]);

  const hits = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return commands.slice(0, 40);
    return commands
      .map((c) => {
        const l = c.label.toLowerCase();
        // exact prefix beats contains, so typing "india_5" lands where you expect
        const score = l.startsWith(t) ? 0 : l.includes(t) ? 1
          : c.group.toLowerCase().includes(t) ? 2 : -1;
        return { c, score };
      })
      .filter((x) => x.score >= 0)
      .sort((a, b) => a.score - b.score)
      .slice(0, 40)
      .map((x) => x.c);
  }, [q, commands]);

  useEffect(() => { setSel(0); }, [q]);

  if (!open) return null;

  const choose = (c: Command) => { c.run(); setOpen(false); };

  let lastGroup = "";
  return (
    <>
      <div className="scrim" onClick={() => setOpen(false)} />
      <div className="palette" role="dialog" aria-modal="true">
        <input
          ref={inputRef} value={q} placeholder="Search scenes, layers, actions…"
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, hits.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
            else if (e.key === "Enter" && hits[sel]) { e.preventDefault(); choose(hits[sel]); }
          }}
        />
        <div className="results">
          {hits.length === 0 && <div className="empty2">No matches for “{q}”</div>}
          {hits.map((c, i) => {
            const head = c.group !== lastGroup ? (lastGroup = c.group) : null;
            return (
              <div key={c.id}>
                {head && <div className="grp">{head}</div>}
                <div className={`item ${i === sel ? "sel" : ""}`}
                  onMouseEnter={() => setSel(i)} onClick={() => choose(c)}>
                  <span>{c.label}</span>
                  {c.hint && <span className="hintkey">{c.hint}</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
