import StampBadge from './StampBadge';
import './ConflictResolver.css';

export default function ConflictResolver({ conflicts, sourcesUsed, onResolve }) {
  if (!conflicts || conflicts.length === 0) return null;

  const referenceLabel = (sourceId) => sourcesUsed.find((s) => s.id === sourceId)?.reference ?? sourceId;

  return (
    <div className="conflict-resolver">
      <div className="conflict-resolver__header">
        <StampBadge variant="reject" />
        <span className="conflict-resolver__title">
          {conflicts.length} source{conflicts.length > 1 ? 's' : ''} disagree — pick one to resolve
        </span>
      </div>

      {conflicts.map((conflict) => (
        <div key={conflict.attribute} className="diff-card">
          <p className="diff-card__attribute">{conflict.attribute.replaceAll('_', ' ')}</p>
          <div className="diff-card__options">
            {conflict.values.map((value, i) => (
              <div key={i} className="diff-card__option">
                <div className="diff-card__option-body">
                  <span className="diff-card__value">{value}</span>
                  <span className="diff-card__source">{referenceLabel(conflict.sources[i])}</span>
                </div>
                <button
                  className="diff-card__resolve"
                  onClick={() => onResolve(conflict.attribute, value, conflict.sources[i])}
                >
                  Resolve &amp; Override
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
