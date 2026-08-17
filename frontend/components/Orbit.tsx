/** The hero visual: a radar satellite imaging the ground from low Earth orbit.
 *
 * Drawn as the actual mechanism rather than a generic space graphic — the satellite
 * rides an inclined orbit, its beam is a side-looking cone (SAR never looks straight
 * down; that is why the geometry works at all), and the lit patch on the limb is the
 * swath the beam is currently illuminating. The expanding rings are the pulse.
 *
 * Pure SVG + CSS so it costs no JavaScript and renders identically on the server. All
 * motion is suspended under prefers-reduced-motion.
 */
export function Orbit() {
  return (
    <div className="orbitwrap" aria-hidden>
      <svg viewBox="0 0 420 420" className="orbit" role="img"
        aria-label="A radar satellite in orbit imaging the Earth's surface">
        <defs>
          <radialGradient id="limb" cx="50%" cy="115%" r="62%">
            <stop offset="0%" stopColor="#0d3b4a" />
            <stop offset="55%" stopColor="#07202b" />
            <stop offset="100%" stopColor="#040d14" />
          </radialGradient>
          <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2ee6c8" stopOpacity=".55" />
            <stop offset="100%" stopColor="#2ee6c8" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="atm" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2ee6c8" stopOpacity=".45" />
            <stop offset="100%" stopColor="#6ba4ff" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Earth limb */}
        <circle cx="210" cy="470" r="270" fill="url(#limb)" />
        <circle cx="210" cy="470" r="270" fill="none" stroke="url(#atm)" strokeWidth="3" />

        {/* graticule — a globe, not a disc */}
        <g className="grat" stroke="#2ee6c8" strokeOpacity=".16" fill="none" strokeWidth=".9">
          <ellipse cx="210" cy="470" rx="270" ry="64" />
          <ellipse cx="210" cy="470" rx="270" ry="132" />
          <ellipse cx="210" cy="470" rx="150" ry="270" />
          <ellipse cx="210" cy="470" rx="242" ry="270" />
        </g>

        {/* the swath currently under the beam */}
        <ellipse className="swath" cx="286" cy="232" rx="52" ry="13" fill="#2ee6c8"
          opacity=".22" />

        {/* orbit path */}
        <ellipse className="orbitpath" cx="210" cy="212" rx="196" ry="70"
          fill="none" stroke="#6ba4ff" strokeOpacity=".28" strokeWidth="1.1"
          strokeDasharray="3 7" transform="rotate(-14 210 212)" />

        {/* satellite: body, panels, and its side-looking beam */}
        <g className="sat">
          <path className="beamcone" d="M0,7 L46,146 L-30,146 Z" fill="url(#beam)" />
          <g className="pulse">
            <path d="M-22,54 A34,34 0 0 0 30,54" fill="none" stroke="#2ee6c8"
              strokeOpacity=".7" strokeWidth="1.6" />
            <path d="M-34,88 A52,52 0 0 0 44,88" fill="none" stroke="#2ee6c8"
              strokeOpacity=".45" strokeWidth="1.4" />
            <path d="M-46,122 A70,70 0 0 0 58,122" fill="none" stroke="#2ee6c8"
              strokeOpacity=".22" strokeWidth="1.2" />
          </g>
          <rect x="-8" y="-8" width="16" height="16" rx="3" fill="#dfe9f5" />
          <rect x="-30" y="-4" width="19" height="8" rx="1.5" fill="#2a4a72" />
          <rect x="11" y="-4" width="19" height="8" rx="1.5" fill="#2a4a72" />
          <circle cx="0" cy="0" r="17" fill="none" stroke="#2ee6c8" strokeOpacity=".3" />
        </g>
      </svg>
    </div>
  );
}
