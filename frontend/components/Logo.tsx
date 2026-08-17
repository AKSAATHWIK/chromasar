/** The ChromaSAR mark — one definition, used everywhere.
 *
 * This is the same squircle-ring the sidebar has always drawn: a conic gradient running
 * teal → blue → deep-teal, with the centre knocked out. It used to exist only as a pair
 * of CSS rules inside `.rail`, which meant the landing page could not show "the logo"
 * without cloning it and letting the two drift. Now the rail imports this too, so there
 * is exactly one mark in the product.
 *
 * `sweep` adds a rotating radar arc inside the ring — the thing the satellite actually
 * does. It is opt-in because a permanently spinning logo in a dense workspace UI is
 * noise; on the landing page it is the point.
 */
export function Logo({ size = 32, sweep = false, className = "" }: {
  size?: number; sweep?: boolean; className?: string;
}) {
  return (
    <span
      className={`cmark ${sweep ? "sweeping" : ""} ${className}`}
      style={{ ["--mk" as string]: `${size}px` }}
      aria-hidden
    >
      <span className="cmark-ring" />
      {sweep && <span className="cmark-sweep" />}
      <span className="cmark-core" />
    </span>
  );
}

/** Wordmark + mark, for headers. */
export function Wordmark({ size = 26, sweep = false }: { size?: number; sweep?: boolean }) {
  return (
    <span className="wordmark">
      <Logo size={size} sweep={sweep} />
      <strong>Chroma<em>SAR</em></strong>
    </span>
  );
}
