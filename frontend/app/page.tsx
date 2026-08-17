import Link from "next/link";
import { HeroScene } from "@/components/HeroScene";
import { Logo, Wordmark } from "@/components/Logo";
import { Boot, Cinema, CountUp, Cursor, Grain, Magnetic, Marquee, Parallax, Pinned,
  Reveal, ScrollProgress, SplitWords, Tilt } from "@/components/Landing";

/** Landing page.
 *
 * Space-themed because the subject genuinely is: a radar satellite in low Earth orbit,
 * firing pulses at the ground and listening for the echo. The hero draws that mechanism
 * rather than a generic space graphic.
 *
 * Every number on this page is measured and matches what the app reports. Overstating a
 * technical product to a technical audience is the fastest way to lose it, and the whole
 * project is built on not doing that.
 */
export const metadata = {
  title: "ChromaSAR — see through the monsoon",
  description:
    "Flood mapping and colorization from Sentinel-1 radar, with calibrated per-pixel " +
    "confidence gating every downstream decision.",
};

const STATS: [string, string, string, string][] = [
  ["0.681", "", "IoU", "flood detection · Sen1Floods11 official test split"],
  ["0.016", "", "ECE", "calibration error after temperature scaling"],
  ["446", "", "scenes", "hand-labelled benchmark chips across 11 regions"],
  ["1.1", "s", "inference", "per scene, on a laptop CPU — no GPU, no cloud"],
];

const ICONS: Record<string, React.ReactNode> = {
  flood: (
    <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round">
      <path className="dr1" d="M3 20c2.4 0 2.4-2 4.8-2s2.4 2 4.8 2 2.4-2 4.8-2 2.4 2 4.8 2 2.4-2 4.8-2" />
      <path className="dr2" d="M3 26c2.4 0 2.4-2 4.8-2s2.4 2 4.8 2 2.4-2 4.8-2 2.4 2 4.8 2 2.4-2 4.8-2" />
      <path d="M16 4v9M12 8l4-4 4 4" opacity=".85" />
    </svg>
  ),
  change: (
    <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 11h17l-4.5-4.5" />
      <path d="M27 21H10l4.5 4.5" />
      <circle className="dr1" cx="24.5" cy="11" r="2.6" />
      <circle className="dr2" cx="7.5" cy="21" r="2.6" />
    </svg>
  ),
  color: (
    <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round">
      <circle cx="16" cy="16" r="11" />
      <path d="M16 5a11 11 0 0 1 0 22z" fill="currentColor" stroke="none" opacity=".5" />
      <circle className="dr1" cx="16" cy="16" r="4.5" opacity=".9" />
    </svg>
  ),
};

const CAPS = [
  {
    key: "flood",
    title: "Flood mapping",
    body:
      "Inundation extent from a single radar pass, in km² of true ground area — computed " +
      "from each scene's own georeferencing, not a nominal pixel size. Permanent water is " +
      "separated from new flooding, because a river is not a disaster.",
    stat: "IoU 0.681",
    href: "/flood",
  },
  {
    key: "change",
    title: "Change detection",
    body:
      "Two passes over one footprint, differenced. Radar is already logarithmic, so the " +
      "classic log-ratio reduces to a plain dB difference — darkening is new water, " +
      "brightening is new roughness. The flood model runs on both dates.",
    stat: "bi-temporal",
    href: "/change",
  },
  {
    key: "color",
    title: "Colorization",
    body:
      "Radar rendered as optical-like imagery, so a responder can read it without years " +
      "of training. Radar carries no colour, so every pixel ships a confidence value — " +
      "below your threshold the system returns grey rather than a guess.",
    stat: "per-pixel confidence",
    href: "/color",
  },
];

/** [number, title, body, image, image caption] — the imagery is the same scene at each
 *  stage of the pipeline, so the section shows the process it is describing. */
const STEPS: [string, string, string, string, string][] = [
  ["01", "Acquire",
   "Sentinel-1 GRD, VV and VH polarisation, calibrated to decibels. Radar penetrates cloud and works at night, so acquisition never waits for weather.",
   "/hero/hero-sar.png", "VV backscatter, −25 to 0 dB"],
  ["02", "Infer",
   "A ResNet34-UNet segments water; a conditional GAN renders colour. Both run on CPU in about a second, in-process, with no network call.",
   "/hero/hero-flood.png", "water probability over the radar"],
  ["03", "Quantify",
   "Ten forward passes with dropout live. Where they agree the model is reading evidence; where they diverge it is inventing, and the map says so.",
   "/hero/hero-conf.png", "per-pixel confidence · teal trusted, amber guessing"],
  ["04", "Gate",
   "Every downstream number is filtered by that confidence. Low-trust regions never raise an alert, and classes we cannot score are not reported at all.",
   "/hero/hero-color.png", "the result the gate lets through"],
];

export default function Landing() {
  return (
    <div className="landing">
      <Boot />
      <Cursor />
      <Grain />
      <ScrollProgress />

      <div className="stars s1" aria-hidden />
      <div className="stars s2" aria-hidden />
      <div className="stars s3" aria-hidden />
      <div className="aurora" aria-hidden />
      <div className="vig" aria-hidden />

      <header className="lnav glass">
        <Wordmark size={26} sweep />
        <nav>
          <Link href="/method">Method</Link>
          <Link href="/flood" className="lcta">Open the app</Link>
        </nav>
      </header>

      <section className="hero">
        <div className="herotext">
          <Reveal>
            <p className="eyebrow"><i className="live-dot" />Sentinel-1 · SAR interpretation</p>
          </Reveal>
          <h1 className="cine-h1">
            <SplitWords text="See through" delay={120} />
            <br />
            <SplitWords text="the monsoon." delay={280} />
          </h1>
          <div className="herobelow">
            <Reveal delay={180}>
              <p className="lead">
                Optical satellites go blind under cloud — exactly when a flood is
                happening. Radar does not. ChromaSAR turns Sentinel-1 backscatter into
                flood maps and readable imagery, and tells you, per pixel, how much of
                it to trust.
              </p>
            </Reveal>
            <Reveal delay={260}>
              <div className="herocta">
                <Magnetic href="/flood" className="btn primary">
                  <span>Open the app</span>
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.9"
                    strokeLinecap="round" strokeLinejoin="round" className="arrow">
                    <path d="M4 10h11M11 6l4 4-4 4" />
                  </svg>
                </Magnetic>
                <Link href="/method" className="btn ghost">See the numbers</Link>
              </div>
            </Reveal>
          </div>
          <Reveal delay={340}>
            <p className="microcopy">
              <Logo size={16} /> Runs on CPU, on one laptop. No network call at inference.
            </p>
          </Reveal>
        </div>
        <Cinema className="heroart">
          <Parallax strength={0.03}>
            <Tilt max={6}><HeroScene /></Tilt>
          </Parallax>
        </Cinema>
      </section>

      <Marquee items={[
        "SENTINEL-1 GRD", "VV + VH POLARISATION", "10 M GROUND SAMPLING",
        "CLOUD-PENETRATING", "MONTE-CARLO DROPOUT", "TEMPERATURE-CALIBRATED",
        "446 BENCHMARK SCENES", "11 REGIONS", "CPU INFERENCE",
      ]} />

      <Reveal as="section" className="statstrip glass" variant="focus">
        {STATS.map(([v, suffix, k, d], i) => (
          <div key={k} className="lstat" style={{ transitionDelay: `${i * 70}ms` }}>
            <b><CountUp value={v} />{suffix}</b>
            <span className="lk">{k}</span>
            <span className="ld">{d}</span>
          </div>
        ))}
      </Reveal>

      <section className="caps">
        {CAPS.map((c, i) => (
          <Reveal key={c.key} delay={i * 110}>
            <Link href={c.href} className="cap glass">
              <span className="capicon">{ICONS[c.key]}</span>
              <h3>{c.title}</h3>
              <p>{c.body}</p>
              <span className="caprow">
                <span className="capstat">{c.stat}</span>
                <span className="capcta">
                  Open
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"
                    strokeLinecap="round" strokeLinejoin="round" className="arrow">
                    <path d="M4 10h11M11 6l4 4-4 4" />
                  </svg>
                </span>
              </span>
            </Link>
          </Reveal>
        ))}
      </section>

      <section className="pipeline">
        <Reveal><p className="eyebrow center">Pulse to decision</p></Reveal>
        <h2 className="ch2"><SplitWords text="Four steps, and one of them is admitting doubt." /></h2>
      </section>
      <Pinned steps={STEPS} />

      <Reveal as="section" className="honest glass" variant="focus">
        <div className="honestinner">
          <p className="eyebrow">The part most demos skip</p>
          <h2 className="ch2"><SplitWords text="It tells you what it cannot do." /></h2>
          <p>
            We tested whether radar alone can break a scene into forest, bare ground and
            built-up area. It cannot: built-up scored an <b>AUC of 0.483</b> against bare
            soil — below chance — and the reference label used to score it calls 26% of
            rural Pakistani flood plain &ldquo;buildings&rdquo;. So the app does not report
            it, and says why on screen.
          </p>
          <p>
            Surface cover comes from the co-registered Sentinel-2 optical chip instead,
            labelled as optical. Water stays with the radar model, which beats optical
            thresholding on the same scenes. <b>A number we cannot score is worse than no
            number.</b>
          </p>
          <Link href="/method" className="btn ghost">How every figure was measured</Link>
        </div>
        {/* the evidence, beside the claim - the right half was empty */}
        <div className="honesttable">
          <div className="htrow hthead"><span>class</span><span>held-out IoU</span><span>verdict</span></div>
          {[["water","52.5%","shipped — but our CNN beats it at 68.1%"],
            ["dense vegetation","54.3%","optical only"],
            ["low vegetation","22.3%","not reported"],
            ["bare ground","13.7%","not reported"],
            ["built-up","0.0%","AUC 0.483 — below chance"]].map(([c,i,v]) => (
            <div className="htrow" key={c}>
              <span>{c}</span><b>{i}</b><span className="htv">{v}</span>
            </div>
          ))}
          <p className="htnote">SAR-only classifier, calibrated on five regions and
            tested on six it had never seen.</p>
        </div>
        <div className="honestglow" aria-hidden />
      </Reveal>

      <Reveal as="section" className="finale" variant="focus">
        <Logo size={56} sweep className="finalemark" />
        <h2 className="ch2"><SplitWords text="Point it at a scene." /></h2>
        <p>446 benchmark scenes are already loaded, or drop in your own GeoTIFF.</p>
        <Magnetic href="/flood" className="btn primary big">
          <span>Open the app</span>
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.9"
            strokeLinecap="round" strokeLinejoin="round" className="arrow">
            <path d="M4 10h11M11 6l4 4-4 4" />
          </svg>
        </Magnetic>
      </Reveal>

      <footer className="lfoot">
        <Wordmark size={20} />
        <span className="spacer" />
        <span>Sen1Floods11 · SEN1-2 · Sentinel-1 GRD</span>
      </footer>
    </div>
  );
}
