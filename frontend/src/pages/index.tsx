import Link from 'next/link';

const features = [
  {
    title: 'Offshore Wind',
    desc: 'Model turbine designs from 8MW to 18MW with real NREL wind resource data across 14 East Coast states.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5">
        <circle cx="12" cy="12" r="2" />
        <path d="M12 10V4M10.3 10.7L6 7M13.7 10.7L18 7" strokeLinecap="round" />
        <path d="M12 14v4M9 14.5l-3 4M15 14.5l3 4" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: 'Wave Energy',
    desc: 'Evaluate Pelamis and RM3 wave devices across continental shelf zones using spectral ocean data.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5">
        <path d="M2 11c1.5-3 3-3 4.5 0s3 3 4.5 0 3-3 4.5 0 3 3 4.5 0" strokeLinecap="round" />
        <path d="M2 16c1.5-3 3-3 4.5 0s3 3 4.5 0 3-3 4.5 0 3 3 4.5 0" strokeLinecap="round" opacity="0.5" />
      </svg>
    ),
  },
  {
    title: 'Ocean Current Kites',
    desc: 'Harness deep ocean currents with hydrokinetic kite designs ranging from 0.05 MW to 2 MW per device.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5">
        <path d="M12 3l3 6 6 1-4.5 4.5 1 6L12 17l-5.5 3.5 1-6L3 10l6-1 3-6z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: 'LCOE Optimization',
    desc: 'Gurobi-powered generation maximization subject to cost constraints and transmission capacity limits.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5">
        <path d="M3 17l4-8 4 4 4-6 4 5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M21 21H3" strokeLinecap="round" />
      </svg>
    ),
  },
];

const stats = [
  { value: '14', label: 'Coastal States' },
  { value: '4', label: 'Energy Technologies' },
  { value: '26+', label: 'Device Designs' },
  { value: 'Gurobi', label: 'Solver' },
];

export default function Home() {
  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="flex flex-col items-center justify-center text-center px-4 pt-28 pb-20">
        <div
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-8 border"
          style={{ borderColor: 'rgba(0,191,99,0.3)', color: '#00BF63', background: 'rgba(0,191,99,0.08)' }}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
          US East Coast &nbsp;·&nbsp; Wind · Wave · Ocean Current
        </div>

        <h1
          className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6 max-w-4xl"
          style={{ color: '#F1F5F9', lineHeight: 1.1 }}
        >
          Offshore Renewable
          <br />
          <span
            style={{
              background: 'linear-gradient(135deg, #00BF63 0%, #38BDF8 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Portfolio Optimizer
          </span>
        </h1>

        <p className="text-lg max-w-2xl mb-10 leading-relaxed" style={{ color: '#94A3B8' }}>
          Mathematically optimize mixed renewable energy portfolios across wind, wave, and ocean
          current technologies. Generate efficient frontiers using real NREL resource data.
        </p>

        <div className="flex flex-col sm:flex-row gap-3">
          <Link
            href="/prototype"
            className="px-7 py-3 rounded-lg text-sm font-semibold text-white transition-all hover:opacity-90 hover:scale-[1.02]"
            style={{
              background: 'linear-gradient(135deg, #00BF63, #00a854)',
              boxShadow: '0 0 24px rgba(0,191,99,0.25)',
            }}
          >
            Launch Optimizer →
          </Link>
          <Link
            href="/about"
            className="px-7 py-3 rounded-lg text-sm font-semibold transition-all hover:bg-white/5"
            style={{ color: '#94A3B8', border: '1px solid rgba(255,255,255,0.1)' }}
          >
            Explore Technologies
          </Link>
        </div>
      </section>

      {/* Stats strip */}
      <section className="px-4 pb-14">
        <div
          className="max-w-3xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-px rounded-xl overflow-hidden"
          style={{ background: 'var(--border)', border: '1px solid var(--border)' }}
        >
          {stats.map((s) => (
            <div
              key={s.label}
              className="flex flex-col items-center py-6 px-4"
              style={{ background: 'var(--surface)' }}
            >
              <span className="text-2xl font-bold mb-1" style={{ color: 'var(--accent)' }}>
                {s.value}
              </span>
              <span className="text-xs" style={{ color: 'var(--muted)' }}>
                {s.label}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Feature cards */}
      <section className="px-4 pb-24 max-w-5xl mx-auto w-full">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-xl p-5 transition-colors"
              style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center mb-4"
                style={{ background: 'rgba(0,191,99,0.1)', color: '#00BF63' }}
              >
                {f.icon}
              </div>
              <h3 className="text-sm font-semibold mb-2" style={{ color: '#F1F5F9' }}>
                {f.title}
              </h3>
              <p className="text-xs leading-relaxed" style={{ color: '#64748B' }}>
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
