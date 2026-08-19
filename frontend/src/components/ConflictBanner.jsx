import StampBadge from './StampBadge';
import './ConflictBanner.css';

export default function ConflictBanner({ conflicts, sourcesUsed }) {
  if (!conflicts || conflicts.length === 0) return null;

  const referenceLabel = (sourceId) => {
    const source = sourcesUsed.find((s) => s.id === sourceId);
    return source ? source.reference : sourceId;
  };

  return (
    <div className="conflict-banner">
      <div className="conflict-banner__header">
        <StampBadge variant="reject" />
        <span className="conflict-banner__title">
          {conflicts.length} source{conflicts.length > 1 ? 's' : ''} disagree
        </span>
      </div>
      {conflicts.map((conflict) => (
        <div key={conflict.attribute} className="conflict-banner__row">
          <span className="conflict-banner__attribute">{conflict.attribute.replaceAll('_', ' ')}</span>
          <div className="conflict-banner__values">
            {conflict.values.map((value, i) => (
              <span key={i} className="conflict-banner__value">
                <strong>{value}</strong>
                <span className="conflict-banner__source"> — {referenceLabel(conflict.sources[i])}</span>
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
