"use client";
import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, type Status } from "@/lib/api";
import { Palette, type Command } from "@/components/Palette";
import { Sidebar, type NavItem } from "@/components/Sidebar";
import { Keys } from "@/components/Keys";
import { TABS, DATASET, ICON } from "@/lib/nav";

/** The application shell.
 *
 * Each workspace is a real route now, not a tab. That buys three things the tab version
 * could not have: a shareable URL for the exact view you are looking at, a working
 * browser back button, and only ONE view mounted at a time - the previous design kept
 * all four alive under `display:none`, which is what let a hidden view's keyboard
 * shortcuts fire and a hidden canvas go stale.
 */
const n = (v: number) => v.toLocaleString("en-US");

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const tab = (TABS.find(([id]) => pathname.startsWith(`/${id}`)) ?? TABS[0])[0];
  const current = TABS.find(([id]) => id === tab)!;

  const [status, setStatus] = useState<Status | null>(null);
  const [sceneCmds, setSceneCmds] = useState<Command[]>([]);
  const [latency, setLatency] = useState<number | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const [keys, setKeys] = useState(false);

  const loaded = [status?.flood_model, status?.color_model].filter(Boolean).length;
  const degraded = !!status && loaded < 2;

  useEffect(() => {
    const h = (e: Event) => {
      const scene = (e as CustomEvent).detail as string;
      setRecent((r) => [scene, ...r.filter((x) => x !== scene)].slice(0, 8));
    };
    window.addEventListener("chromasar:scene", h);
    window.addEventListener("chromasar:opened", h);
    return () => {
      window.removeEventListener("chromasar:scene", h);
      window.removeEventListener("chromasar:opened", h);
    };
  }, []);

  useEffect(() => {
    const t0 = performance.now();
    api.status().then((s) => { setStatus(s); setLatency(performance.now() - t0); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    api.floodSamples(500).then((d) => {
      const cmds: Command[] = [];
      for (const [region, chips] of Object.entries(d.regions)) {
        for (const c of chips) {
          cmds.push({
            id: `scene:${c}`, group: `Scenes · ${region}`, label: c, hint: "open",
            run: () => {
              router.push("/flood");
              window.dispatchEvent(new CustomEvent("chromasar:scene", { detail: c }));
            },
          });
        }
      }
      setSceneCmds(cmds);
    }).catch(() => {});
  }, [router]);

  const commands = useMemo<Command[]>(() => [
    ...TABS.map(([id, label], i) => ({
      id: `tab:${id}`, group: "Go to", label, hint: `${i + 1}`,
      run: () => router.push(`/${id}`),
    })),
    { id: "act:run", group: "Actions", label: "Run detection on current scene",
      hint: "R", run: () => window.dispatchEvent(new CustomEvent("chromasar:run")) },
    { id: "act:perm", group: "Actions", label: "Toggle permanent-water exclusion",
      hint: "P", run: () => window.dispatchEvent(new CustomEvent("chromasar:perm")) },
    { id: "act:sweep", group: "Actions", label: "Sweep the whole region",
      hint: "B", run: () => window.dispatchEvent(new CustomEvent("chromasar:sweep")) },
    { id: "act:keys", group: "Actions", label: "Keyboard shortcuts", hint: "?",
      run: () => setKeys(true) },
    { id: "act:home", group: "Actions", label: "Back to the landing page", hint: "",
      run: () => router.push("/") },
    ...sceneCmds,
  ], [sceneCmds, router]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(t.tagName)) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key >= "1" && e.key <= "4") router.push(`/${TABS[+e.key - 1][0]}`);
      else if (e.key === "?") setKeys(true);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [router]);

  return (
    <div className="app">
      <Sidebar
        items={TABS.map(([id, label, desc]) => ({ id, label, desc, icon: ICON[id] })) as NavItem[]}
        active={tab}
        onSelect={(id) => router.push(`/${id}`)}
        status={status}
        recent={recent}
        onRecent={(scene) => {
          router.push("/flood");
          window.dispatchEvent(new CustomEvent("chromasar:scene", { detail: scene }));
        }}
      />

      <header className="topbar">
        <div className="crumb">
          <h1>Chroma<em>SAR</em></h1>
          <span className="sep">/</span>
          <span className="sub">{current[1]} — {current[2]}</span>
        </div>
        <div className="spacer" />
        <div className="topright">
          <button className="cmdk" onClick={() =>
            window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true }))}>
            <span>Search scenes and actions</span>
            <span className="spacer" />
            <kbd>Ctrl</kbd><kbd>K</kbd>
          </button>
          <div className={`sysbar statuses ${degraded ? "degraded" : ""}`}>
            {status ? (
              <>
                <span><i className={`dot ${degraded ? "bad" : "ok"}`} />
                  <b>{status.device.toUpperCase()}</b></span>
                <span><span className="k">models</span><b>{loaded}/2</b></span>
                <span><span className="k">T</span><b>{status.temperature.toFixed(3)}</b></span>
              </>
            ) : <span><i className="dot" />connecting…</span>}
          </div>
          <span className={`pill pillmini ${status ? "on" : "off"}`}>
            <i className="dot" />
            {status ? `${status.device.toUpperCase()} · ${loaded}/2` : "…"}
          </span>
          <button className="mini ghosticon" aria-label="keyboard shortcuts"
            title="Keyboard shortcuts (?)" onClick={() => setKeys(true)}>?</button>
        </div>
      </header>

      <main className="work">{children}</main>

      <footer className="statusbar">
        <span className="f"><span>workspace</span><b>{current[1]}</b></span>
        <span className="rule" />
        <span className="f"><span>scene</span><b>{recent[0] ?? "none selected"}</b></span>
        <span className="spacer" />
        {latency !== null && (
          <><span className="f"><span>handshake</span><b>{latency.toFixed(0)} ms</b></span>
            <span className="rule" /></>
        )}
        <span className="f"><span>corpus</span><b>{
          !status || tab === "change" ? DATASET[tab]
            : tab === "color" ? `${DATASET[tab]} · ${n(status.sar_pairs)} pairs`
              : `${DATASET[tab]} · ${n(status.flood_chips)} chips`
        }</b></span>
      </footer>

      <Palette commands={commands} />
      {keys && <Keys onClose={() => setKeys(false)} />}
    </div>
  );
}
