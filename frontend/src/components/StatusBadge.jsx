const VARIANTS = {
  grounded: {
    label: 'Grounded',
    classes: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  },
  unverified: {
    label: 'Unverified',
    classes: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  },
  conflict: {
    label: 'Conflict',
    classes: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  },
};

export default function StatusBadge({ classification }) {
  const config = VARIANTS[classification] ?? VARIANTS.unverified;
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide ${config.classes}`}
    >
      {config.label}
    </span>
  );
}
