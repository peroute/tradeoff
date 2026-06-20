// The human-in-the-loop boundary, made structural rather than incidental.
// Per the brief this banner MUST be pinned, always visible, and on a contrasting
// background — it is the visible promise that the AI never makes the decision.
export default function HumanBoundaryBanner() {
  return (
    <div
      role="note"
      aria-label="Human decision boundary"
      className="sticky top-0 z-40 border-b border-signal/40 bg-signal/15 backdrop-blur-md"
    >
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-2.5 sm:px-6">
        <svg
          width="18"
          height="18"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden
          className="shrink-0 text-signal"
        >
          <path d="M8 2 L13.5 4.2 V8 c0 3.4 -2.4 5.4 -5.5 6.4 C4.9 13.4 2.5 11.4 2.5 8 V4.2 Z" />
          <path d="M5.8 8.2 L7.3 9.7 L10.3 6.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <p className="text-[13px] leading-snug text-ink">
          <span className="font-semibold">You make the call.</span>{' '}
          <span className="text-ink-muted">
            This tool lays out the trade-offs from cited data — it never recommends which country to
            choose.
          </span>
        </p>
      </div>
    </div>
  )
}
