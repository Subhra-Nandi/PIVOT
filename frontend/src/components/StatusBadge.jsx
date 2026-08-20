const VARIANTS = {
  extracted: {
    label: 'Grounded',
    classes: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  },
  inferred: {
    label: 'Unverified',
    classes: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  },
  needs_review: {
    label: 'Conflict',
    classes: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  },
};

export default function StatusBadge({ status, label }) {
  const config = VARIANTS[status] ?? VARIANTS.inferred;
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide ${config.classes}`}
    >
      {label ?? config.label}
    </span>
  );
}
