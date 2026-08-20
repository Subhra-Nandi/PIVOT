import './TrustHUD.css';

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function gaugeVariant(confidence) {
  if (confidence >= 0.8) return 'pass';
  if (confidence >= 0.5) return 'note';
  return 'hold';
}

export default function TrustHUD({ record, statusFilter, onFilterChange }) {
  const specs = record.specifications;
  const confidence = record.validation?.overall_confidence ?? 0;
  const conflictCount = record.validation?.conflicts?.length ?? 0;
  const groundedCount = specs.filter((s) => s.status === 'extracted').length;
  const reviewCount = specs.filter((s) => s.status === 'needs_review').length;
  const inferredCount = specs.filter((s) => s.status === 'inferred').length;
  const offset = CIRCUMFERENCE * (1 - confidence);

  function togglePill(value) {
    onFilterChange(statusFilter === value ? null : value);
  }

  return (
    <header className="hud">
      <div className="hud__title-block">
        <p className="hud__eyebrow">Product Intelligence — Inspection Report</p>
        <h1 className="hud__title">PIVOT</h1>
        <p className="hud__subtitle">
          Every field on this record traces back to a source, a page, and a
          confidence score. Click a pill to filter, click a field to prove it.
        </p>
      </div>

      <div className="hud__panel">
        <div className={`gauge gauge--${gaugeVariant(confidence)}`}>
          <svg viewBox="0 0 120 120" className="gauge__ring" aria-hidden="true">
            <circle cx="60" cy="60" r={RADIUS} className="gauge__track" />
            <circle
              cx="60"
              cy="60"
              r={RADIUS}
              className="gauge__fill"
              style={{ strokeDasharray: CIRCUMFERENCE, strokeDashoffset: offset }}
            />
          </svg>
          <div className="gauge__label">
            <span className="gauge__value">{Math.round(confidence * 100)}%</span>
            <span className="gauge__caption">Record Integrity</span>
          </div>
        </div>

        <div className="hud__pills" role="group" aria-label="Filter fields by status">
          <button
            className={`pill pill--pass ${statusFilter === 'extracted' ? 'pill--active' : ''}`}
            onClick={() => togglePill('extracted')}
          >
            {groundedCount} Grounded
          </button>
          <button
            className={`pill pill--hold ${statusFilter === 'needs_review' ? 'pill--active' : ''}`}
            onClick={() => togglePill('needs_review')}
            disabled={reviewCount === 0}
          >
            {reviewCount} Unverified
          </button>
          <button
            className={`pill pill--conflict ${statusFilter === 'conflict' ? 'pill--active' : ''}`}
            onClick={() => togglePill('conflict')}
            disabled={conflictCount === 0}
          >
            {conflictCount} Conflict{conflictCount === 1 ? '' : 's'}
          </button>
          {inferredCount > 0 && (
            <button
              className={`pill pill--note ${statusFilter === 'inferred' ? 'pill--active' : ''}`}
              onClick={() => togglePill('inferred')}
            >
              {inferredCount} Inferred
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
