// Brand mark: two paths (teal A, amber B) converging on a single decision node.
// The same metaphor the loading screen animates and the whole product is built on.

interface LogoProps {
  className?: string
  /** Pixel size of the square glyph. */
  size?: number
  title?: string
}

export default function Logo({ className, size = 28, title = 'Tradeoff' }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      role="img"
      aria-label={title}
      className={className}
    >
      <path
        d="M5 7 L16 19"
        className="stroke-path-a"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M27 7 L16 19"
        className="stroke-path-b"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M16 19 L16 27"
        className="stroke-ink"
        strokeWidth="2.5"
        strokeLinecap="round"
        opacity="0.55"
      />
      <circle cx="16" cy="19" r="3.2" className="fill-ink" />
      <circle cx="16" cy="19" r="6" className="stroke-ink" strokeWidth="1" opacity="0.25" />
    </svg>
  )
}
