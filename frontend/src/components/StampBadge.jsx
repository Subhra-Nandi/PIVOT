import './StampBadge.css';

const VARIANTS = {
  pass: { label: 'VERIFIED', className: 'stamp--pass' },
  note: { label: 'INFERRED', className: 'stamp--note' },
  hold: { label: 'REVIEW', className: 'stamp--hold' },
  reject: { label: 'CONFLICT', className: 'stamp--reject' },
};

/** Renders a status as an inked rubber-stamp mark — the recurring motif
 * tying the UI to the subject: this is a QC inspection tag, and every
 * field gets stamped the way a real inspected part would be. */
export default function StampBadge({ variant, label, size = 'sm' }) {
  const config = VARIANTS[variant] ?? VARIANTS.note;
  return (
    <span className={`stamp ${config.className} stamp--${size}`}>
      {label ?? config.label}
    </span>
  );
}

export function statusToVariant(status) {
  if (status === 'extracted') return 'pass';
  if (status === 'inferred') return 'note';
  if (status === 'needs_review') return 'hold';
  return 'note';
}
