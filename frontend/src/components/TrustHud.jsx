const PILL_CONFIG = {
  extracted: {
    label: 'Grounded',
    activeClasses: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    dot: 'bg-emerald-400',
  },
  inferred: {
    label: 'Unverified',
    activeClasses: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    dot: 'bg-amber-400',
  },
  needs_review: {
    label: 'Conflict',
    activeClasses: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    dot: 'bg-rose-400',
  },
};

function ConfidenceRing({ value }) {
  const pct = Math.round((value ?? 0) * 100);
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - (value ?? 0));

  return (
    <div className="relative h-16 w-16 shrink-0">
      <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90">
        <circle cx="32" cy="32" r={radius} fill="none" stroke="#27272a" strokeWidth="6" />
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          stroke="url(#limeGradient)"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-500 ease-out"
          style={{ filter: 'drop-shadow(0 0 4px rgba(163,230,53,0.6))' }}
        />
        <defs>
          <linearGradient id="limeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#a3e635" />
            <stop offset="100%" stopColor="#65a30d" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-sm font-semibold text-lime-400">{pct}%</span>
      </div>
    </div>
  );
}

function FilterPill({ statusKey, count, active, onClick }) {
  const config = PILL_CONFIG[statusKey];
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 font-mono text-xs transition-all duration-200 ${
        active
          ? config.activeClasses
          : 'border-zinc-800 bg-zinc-900/80 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} aria-hidden="true" />
      {count} {config.label}
    </button>
  );
}

export default function TrustHud({ overallConfidence, counts, activeFilter, onFilterChange }) {
  const hasConfidence = typeof overallConfidence === 'number';

  function toggle(statusKey) {
    onFilterChange(activeFilter === statusKey ? null : statusKey);
  }

  return (
    <header className="sticky top-0 z-10 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 animate-pulse rounded-full bg-lime-400" aria-hidden="true" />
              <h1 className="font-display text-xl font-bold tracking-tight text-zinc-100">PIVOT</h1>
            </div>
            <p className="mt-0.5 font-mono text-[11px] text-zinc-500">
              Product intelligence &mdash; verified, not assumed
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <FilterPill
            statusKey="extracted"
            count={counts.grounded}
            active={activeFilter === 'extracted'}
            onClick={() => toggle('extracted')}
          />
          <FilterPill
            statusKey="inferred"
            count={counts.unverified}
            active={activeFilter === 'inferred'}
            onClick={() => toggle('inferred')}
          />
          <FilterPill
            statusKey="needs_review"
            count={counts.conflict}
            active={activeFilter === 'needs_review'}
            onClick={() => toggle('needs_review')}
          />

          {hasConfidence && (
            <div className="ml-1 flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/80 px-3 py-2">
              <ConfidenceRing value={overallConfidence} />
              <div className="leading-tight">
                <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                  Record
                </p>
                <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                  Integrity
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
