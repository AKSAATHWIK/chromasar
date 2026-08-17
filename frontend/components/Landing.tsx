"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";

/* ────────────────────────────────────────────────────────────────────────────
   Client-side motion for the landing page.

   Everything here degrades to static: if the observer never fires, content is
   already visible; if the cursor never mounts, the native one is untouched; if
   prefers-reduced-motion is set, nothing animates at all. A landing page that
   hides its content behind an animation that failed is worse than no animation.
   ──────────────────────────────────────────────────────────────────────────── */

const reduced = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** A glowing dot that tracks the pointer, with a ring that lags behind it.
 *
 * Position is written straight to the element's transform inside rAF rather than
 * through React state — a setState per mousemove would re-render the whole page at
 * pointer frequency. Hidden entirely on touch devices, which have no cursor to replace.
 */
export function Cursor() {
  const dot = useRef<HTMLDivElement>(null);
  const ring = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (reduced() || window.matchMedia("(hover: none)").matches) return;
    document.body.classList.add("has-cursor");

    let x = innerWidth / 2, y = innerHeight / 2;
    let rx = x, ry = y, raf = 0;

    const move = (e: PointerEvent) => {
      x = e.clientX; y = e.clientY;
      if (dot.current) dot.current.style.transform = `translate(${x}px, ${y}px)`;
      const t = e.target as HTMLElement;
      const hot = !!t.closest?.("a, button, [role=button]");
      ring.current?.classList.toggle("hot", hot);
    };
    const loop = () => {
      rx += (x - rx) * 0.18;           // the lag is the whole effect
      ry += (y - ry) * 0.18;
      if (ring.current) ring.current.style.transform = `translate(${rx}px, ${ry}px)`;
      raf = requestAnimationFrame(loop);
    };
    const down = () => ring.current?.classList.add("down");
    const up = () => ring.current?.classList.remove("down");
    const leave = () => { dot.current?.classList.add("gone"); ring.current?.classList.add("gone"); };
    const enter = () => { dot.current?.classList.remove("gone"); ring.current?.classList.remove("gone"); };

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerdown", down);
    window.addEventListener("pointerup", up);
    document.addEventListener("pointerleave", leave);
    document.addEventListener("pointerenter", enter);
    raf = requestAnimationFrame(loop);
    return () => {
      document.body.classList.remove("has-cursor");
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerdown", down);
      window.removeEventListener("pointerup", up);
      document.removeEventListener("pointerleave", leave);
      document.removeEventListener("pointerenter", enter);
    };
  }, []);

  return (
    <>
      <div ref={ring} className="cursor-ring" aria-hidden />
      <div ref={dot} className="cursor-dot" aria-hidden />
    </>
  );
}

/** Reveal on scroll. `delay` staggers siblings without hand-written timeouts. */
export function Reveal({ children, delay = 0, as: Tag = "div", className = "",
  variant = "rise" }: {
  children: ReactNode; delay?: number; as?: "div" | "section" | "li"; className?: string;
  /** rise = lift and fade. focus = comes in out of focus, like a rack focus. */
  variant?: "rise" | "focus";
}) {
  const ref = useRef<HTMLElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduced() || !("IntersectionObserver" in window)) { setShown(true); return; }
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect(); } },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.08 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    // @ts-expect-error - polymorphic tag, ref type widens correctly at runtime
    <Tag ref={ref} className={`reveal rv-${variant} ${shown ? "in" : ""} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </Tag>
  );
}

/** Counts a number up when it scrolls into view.
 *
 * Formats from the target string so "24 × 7" and "0.681" both survive — the animation
 * only runs when the value is actually numeric.
 */
export function CountUp({ value, duration = 1100 }: { value: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [text, setText] = useState(() => {
    const n = Number(value);
    return Number.isFinite(n) ? "0".padEnd(value.length, " ") : value;
  });

  useEffect(() => {
    const el = ref.current;
    const target = Number(value);
    if (!el || !Number.isFinite(target)) { setText(value); return; }
    if (reduced()) { setText(value); return; }
    const decimals = (value.split(".")[1] ?? "").length;

    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const t0 = performance.now();
      const tick = (now: number) => {
        const k = Math.min(1, (now - t0) / duration);
        const eased = 1 - Math.pow(1 - k, 3);
        setText((target * eased).toFixed(decimals));
        if (k < 1) requestAnimationFrame(tick);
        else setText(value);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.4 });
    io.observe(el);
    return () => io.disconnect();
  }, [value, duration]);

  return <span ref={ref} className="countup">{text}</span>;
}

/** Buttons that lean toward the pointer. Subtle — 6px at the extreme. */
export function Magnetic({ children, className = "", href }: {
  children: ReactNode; className?: string; href: string;
}) {
  const ref = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || reduced() || window.matchMedia("(hover: none)").matches) return;
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const dx = (e.clientX - (r.left + r.width / 2)) / r.width;
      const dy = (e.clientY - (r.top + r.height / 2)) / r.height;
      el.style.transform = `translate(${dx * 12}px, ${dy * 8}px)`;
    };
    const out = () => { el.style.transform = ""; };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", out);
    return () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", out);
    };
  }, []);

  return <a ref={ref} href={href} className={className}>{children}</a>;
}

/** The boot sequence: a brief scan-line pass while the first paint settles.
 *
 * Capped hard at 1.1s and removed on load — a splash screen that can outlive the page
 * is a bug, not a brand moment.
 */
export function Boot() {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (reduced()) { setDone(true); return; }
    const t = setTimeout(() => setDone(true), 1100);
    return () => clearTimeout(t);
  }, []);
  if (done) return null;
  return (
    <div className="boot" aria-hidden>
      <div className="bootinner">
        <div className="bootbar"><i /></div>
        <span>acquiring scene…</span>
      </div>
    </div>
  );
}

/** Parallax: nudges its child against scroll. */
export function Parallax({ children, strength = 0.06, className = "" }: {
  children: ReactNode; strength?: number; className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || reduced()) return;
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        el.style.transform = `translateY(${window.scrollY * strength}px)`;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { window.removeEventListener("scroll", onScroll); cancelAnimationFrame(raf); };
  }, [strength]);
  return <div ref={ref} className={className}>{children}</div>;
}

/* ────────────────────────────────────────────────────────────────────────────
   Cinematics. The difference between "animated" and "cinematic" is that
   cinematic motion is driven by the viewer — you scrub it — and it has weight.
   These are all scroll-linked or staged, none of them loop for their own sake.
   ──────────────────────────────────────────────────────────────────────────── */

/** A hairline that fills as you move through the page. Orientation, not decoration. */
export function ScrollProgress() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const max = document.body.scrollHeight - innerHeight;
        el.style.transform = `scaleX(${max > 0 ? scrollY / max : 0})`;
      });
    };
    on();
    window.addEventListener("scroll", on, { passive: true });
    window.addEventListener("resize", on);
    return () => {
      window.removeEventListener("scroll", on);
      window.removeEventListener("resize", on);
      cancelAnimationFrame(raf);
    };
  }, []);
  return <div className="scrollprog" aria-hidden><i ref={ref} /></div>;
}

/** Title-sequence reveal: each word rises from behind a mask edge.
 *
 * The text stays a single readable string for screen readers and for copy-paste; the
 * masking is purely visual, one span per word.
 */
export function SplitWords({ text, delay = 0, className = "" }: {
  text: string; delay?: number; className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduced() || !("IntersectionObserver" in window)) { setShown(true); return; }
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setShown(true); io.disconnect(); }
    }, { threshold: 0.2 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <span ref={ref} className={`splitw ${shown ? "in" : ""} ${className}`}>
      <span className="sr-only">{text}</span>
      {text.split(" ").map((w, i) => (
        <span className="wmask" key={`${w}-${i}`} aria-hidden>
          <span className="word" style={{ transitionDelay: `${delay + i * 65}ms` }}>
            {w}
          </span>
        </span>
      ))}
    </span>
  );
}

/** Animated film grain. Cheap: one tiny SVG turbulence tile, nudged each frame. */
export function Grain() {
  const [on, setOn] = useState(false);
  useEffect(() => { setOn(!reduced()); }, []);
  if (!on) return null;
  return <div className="grain" aria-hidden />;
}

/** Scroll-linked scale + lift for a hero element. Gives the opening real depth:
 *  the frame settles back as the page moves, the way a camera pulls focus. */
export function Cinema({ children, className = "" }: {
  children: ReactNode; className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || reduced()) return;
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const k = Math.min(1, Math.max(0, scrollY / (innerHeight * 0.9)));
        el.style.transform = `perspective(1400px) rotateX(${k * 7}deg) scale(${1 - k * 0.1})`;
        el.style.opacity = `${1 - k * 0.42}`;
      });
    };
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => { window.removeEventListener("scroll", on); cancelAnimationFrame(raf); };
  }, []);
  return <div ref={ref} className={className}>{children}</div>;
}

/** An infinite ticker. The content is duplicated once and the track translates by
 *  exactly -50%, so the loop point is seamless without measuring anything. */
export function Marquee({ items, speed = 38 }: { items: string[]; speed?: number }) {
  const run = [...items, ...items];
  return (
    <div className="marquee" aria-hidden>
      <div className="mqtrack" style={{ animationDuration: `${speed}s` }}>
        {run.map((t, i) => (
          <span key={i} className="mqitem">
            {t}
            <i className="mqdot" />
          </span>
        ))}
      </div>
    </div>
  );
}

/** Tilts its child toward the pointer in 3D. Used on the hero frame so the imagery
 *  feels like an object under glass rather than a flat placement. */
export function Tilt({ children, max = 7, className = "" }: {
  children: ReactNode; max?: number; className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || reduced() || window.matchMedia("(hover: none)").matches) return;
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
      const dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
      el.style.transform =
        `perspective(1200px) rotateY(${dx * max}deg) rotateX(${-dy * max}deg) scale(1.015)`;
    };
    const out = () => { el.style.transform = ""; };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", out);
    return () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", out);
    };
  }, [max]);
  return <div ref={ref} className={`tilt ${className}`}>{children}</div>;
}

/** Scroll-pinned sequence: the section sticks while its steps advance.
 *
 * The first version was text alone on a 100vh stage — one heading and three lines
 * floating in a screen of black, which read as a layout failure rather than a pause.
 * Each step now drives the imagery too: you watch the same scene go from raw radar, to
 * a water probability, to the model's own uncertainty, to the gated result. That is the
 * pipeline the words are describing, so the pin is finally doing work.
 *
 * The pin is a plain `position: sticky` child inside a tall parent — no scroll
 * hijacking, no preventDefault. The wheel keeps doing exactly what the user expects,
 * which is the difference between cinematic and infuriating.
 */
export function Pinned({ steps }: {
  steps: [string, string, string, string, string][];
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const total = r.height - innerHeight;
        if (total <= 0) return;
        const k = Math.min(0.999, Math.max(0, -r.top / total));
        setActive(Math.floor(k * steps.length));
      });
    };
    on();
    window.addEventListener("scroll", on, { passive: true });
    window.addEventListener("resize", on);
    return () => {
      window.removeEventListener("scroll", on);
      window.removeEventListener("resize", on);
      cancelAnimationFrame(raf);
    };
  }, [steps.length]);

  return (
    <div className="pinwrap" ref={wrap} style={{ height: `${steps.length * 72}vh` }}>
      <div className="pinstage">
        <div className="pincol">
          <div className="pinrail" aria-hidden>
            {steps.map(([n], i) => (
              <button key={n} className={i === active ? "on" : i < active ? "past" : ""}
                onClick={() => {
                  const el = wrap.current;
                  if (!el) return;
                  const total = el.offsetHeight - innerHeight;
                  scrollTo({ top: el.offsetTop + total * ((i + 0.5) / steps.length),
                             behavior: "smooth" });
                }}>
                <i />{n}
              </button>
            ))}
          </div>
          <div className="pinbody">
            {steps.map(([n, t, b], i) => (
              <div key={n} className={`pinstep ${i === active ? "on" : ""}`}>
                <h3>{t}</h3>
                <p>{b}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="pinart">
          {steps.map(([n, , , src, cap], i) => (
            <figure key={n} className={`pinframe ${i === active ? "on" : ""}`}>
              <img src={src} alt="" draggable={false} />
              <span className="tick tl" /><span className="tick tr" />
              <span className="tick bl" /><span className="tick br" />
              <figcaption>{cap}</figcaption>
            </figure>
          ))}
        </div>
      </div>
    </div>
  );
}
