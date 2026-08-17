"use client";
import { useEffect, useRef, useState } from "react";

/** The hero: real Sentinel-1 data, wiped between real model outputs.
 *
 * The previous hero was a vector satellite orbiting a wireframe globe, and it was
 * clip-art — the satellite sat inside the planet and its beam fired into the interior.
 * Sites that read as expensive do not draw a diagram of the product; they show the
 * product very large with almost nothing around it.
 *
 * These are genuine 512×512 frames exported from the pipeline (chromasar/scripts/
 * make_hero.py): calibrated VV backscatter, the water probability the flood model
 * assigns it, the colorization generator's output, and the per-pixel confidence map.
 * The scan line is the wipe boundary, so the motion is doing work rather than
 * decorating — you are watching radar turn into an answer.
 */
const FRAMES = [
  { src: "/hero/hero-sar.png", label: "Sentinel-1 VV", meta: "raw backscatter, dB" },
  { src: "/hero/hero-flood.png", label: "Water probability", meta: "calibrated, T = 1.368" },
  { src: "/hero/hero-color.png", label: "Colorized", meta: "conditional GAN" },
  { src: "/hero/hero-conf.png", label: "Confidence", meta: "10-pass MC dropout" },
];

const DWELL = 3200;
/** The opening frame holds longer. A visitor should register that they are looking at
 *  raw radar - the "before" the whole product argues from - before it starts turning
 *  into anything else. */
const FIRST_DWELL = 5200;

export function HeroScene() {
  const [i, setI] = useState(0);
  const [wiping, setWiping] = useState(false);
  const hold = useRef(false);
  const iRef = useRef(0);
  useEffect(() => { iRef.current = i; }, [i]);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let t: ReturnType<typeof setTimeout>;
    const cycle = () => {
      t = setTimeout(() => {
        if (!hold.current) {
          setWiping(true);
          setTimeout(() => { setI((v) => (v + 1) % FRAMES.length); setWiping(false); }, 900);
        }
        cycle();
      }, iRef.current === 0 ? FIRST_DWELL : DWELL);
    };
    cycle();
    return () => clearTimeout(t);
  }, []);

  const cur = FRAMES[i];
  const next = FRAMES[(i + 1) % FRAMES.length];

  return (
    <figure
      className={`heroscene ${wiping ? "wiping" : ""}`}
      onPointerEnter={() => { hold.current = true; }}
      onPointerLeave={() => { hold.current = false; }}
    >
      <div className="hsframe">
        {/* the frame furniture: corner ticks and a graticule, like an analyst's viewer */}
        <span className="tick tl" /><span className="tick tr" />
        <span className="tick bl" /><span className="tick br" />
        <div className="hsgrid" aria-hidden />

        <img src={cur.src} alt={cur.label} className="hsimg" draggable={false} />
        <img src={next.src} alt="" aria-hidden className="hsimg hsnext" draggable={false} />
        <div className="hsscan" aria-hidden />
        <div className="hsvig" aria-hidden />

        <figcaption className="hscap">
          <span className="hsdot" />
          <b>{cur.label}</b>
          <span className="hsmeta">{cur.meta}</span>
        </figcaption>

        <div className="hsprog" aria-hidden>
          {FRAMES.map((f, k) => (
            <i key={f.src} className={k === i ? "on" : ""} />
          ))}
        </div>
      </div>

      <figcaption className="hsfoot">
        India_1018317 · 26.5614°N 92.7924°E · Brahmaputra valley, Assam
      </figcaption>
    </figure>
  );
}
