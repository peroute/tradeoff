// Calm "instrument panel" backdrop shared by intake and loading for visual continuity.
// A faint engineering grid plus two opposed radial glows (teal left = path A, amber
// right = path B) that spatially echo the A-vs-B duality. Deliberately low-contrast so
// it reads as atmosphere, never decoration competing with content.

export default function AmbientBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-paper">
      {/* Engineering grid */}
      <div
        className="absolute inset-0 opacity-[0.5]"
        style={{
          backgroundImage:
            'linear-gradient(to right, #2A3949 1px, transparent 1px), linear-gradient(to bottom, #2A3949 1px, transparent 1px)',
          backgroundSize: '64px 64px',
          maskImage: 'radial-gradient(ellipse 80% 60% at 50% 38%, #000 35%, transparent 100%)',
          WebkitMaskImage:
            'radial-gradient(ellipse 80% 60% at 50% 38%, #000 35%, transparent 100%)',
          opacity: 0.12,
        }}
      />
      {/* Path A glow (teal, left) */}
      <div
        className="absolute -left-32 top-1/4 h-[34rem] w-[34rem] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(circle, rgba(60,174,189,0.16), transparent 65%)' }}
      />
      {/* Path B glow (amber, right) */}
      <div
        className="absolute -right-32 top-1/3 h-[34rem] w-[34rem] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(circle, rgba(224,162,74,0.13), transparent 65%)' }}
      />
      {/* Convergence wash at center-bottom — where the two paths meet */}
      <div
        className="absolute bottom-0 left-1/2 h-[26rem] w-[40rem] -translate-x-1/2 blur-3xl"
        style={{ background: 'radial-gradient(ellipse, rgba(60,174,189,0.06), transparent 70%)' }}
      />
    </div>
  )
}
