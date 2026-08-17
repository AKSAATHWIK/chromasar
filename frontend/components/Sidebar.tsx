"use client";
import { useEffect, useState } from "react";
import type { Status } from "@/lib/api";
import Link from "next/link";
import { Logo } from "./Logo";

export type NavItem = {
  id: string; label: string; desc: string; icon: React.ReactNode;
};

/** Collapsible navigator.
 *
 * Collapsed it is a 60px icon rail; expanded it shows labels, a one-line description
 * of each workspace, live model state and the scenes you have already opened. The
 * width is persisted, because a tool that forgets how you left it feels cheap. */
export function Sidebar({ items, active, onSelect, status, recent, onRecent }: {
  items: NavItem[];
  active: string;
  onSelect: (id: string) => void;
  status: Status | null;
  recent: string[];
  onRecent: (scene: string) => void;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const v = localStorage.getItem("chromasar.sidebar");
    if (v) setOpen(v === "1");
  }, []);
  const toggle = () => {
    setOpen((v) => {
      localStorage.setItem("chromasar.sidebar", v ? "0" : "1");
      return !v;
    });
  };

  return (
    <nav className={`rail ${open ? "wide" : ""}`}>
      <div className="railhead">
        {/* the mark is the way back out of the workspace */}
        <Link href="/" className="railhome" aria-label="ChromaSAR home" title="Home">
          <Logo size={32} />
        </Link>
        {open && (
          <div className="railbrand">
            <strong>Chroma<em>SAR</em></strong>
            <span>Sentinel-1 analysis</span>
          </div>
        )}
      </div>

      {open && <div className="railgrp">Workspaces</div>}
      {items.map((it) => (
        <button key={it.id} className={active === it.id ? "on" : ""} data-tip={it.label}
          aria-label={it.label} onClick={() => onSelect(it.id)}>
          <span className="ico">{it.icon}</span>
          {open && (
            <span className="txt">
              <b>{it.label}</b>
              <i>{it.desc}</i>
            </span>
          )}
        </button>
      ))}

      {open && recent.length > 0 && (
        <>
          <div className="railgrp">Recent scenes</div>
          <div className="recent">
            {recent.slice(0, 6).map((r) => (
              <button key={r} className="recentitem" onClick={() => onRecent(r)}>
                {r}
              </button>
            ))}
          </div>
        </>
      )}

      <div className="spacer" />

      {open && status && (
        <div className="railstatus">
          <div className="railgrp">Runtime</div>
          <div className="kv"><span>device</span><b>{status.device.toUpperCase()}</b></div>
          <div className="kv"><span>flood model</span>
            <b className={status.flood_model ? "ok" : "bad"}>
              {status.flood_model ? "loaded" : "missing"}</b></div>
          <div className="kv"><span>colorization</span>
            <b className={status.color_model ? "ok" : "bad"}>
              {status.color_model ? "loaded" : "missing"}</b></div>
          <div className="kv"><span>calibration</span><b>T={status.temperature}</b></div>
          <div className="kv"><span>benchmark</span><b>{status.flood_chips} chips</b></div>
        </div>
      )}

      <button className="railtoggle" onClick={toggle}
        data-tip={open ? "Collapse" : "Expand"} aria-label="toggle sidebar">
        <span className="ico">{open ? "‹" : "›"}</span>
        {open && <span className="txt"><b>Collapse</b></span>}
      </button>
    </nav>
  );
}
