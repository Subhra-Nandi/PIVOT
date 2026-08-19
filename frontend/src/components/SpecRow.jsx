import { useState } from 'react';
import StampBadge, { statusToVariant } from './StampBadge';
import './SpecRow.css';

export default function SpecRow({ spec, resolvedSource }) {
  const [open, setOpen] = useState(false);
  const hasCitation = Boolean(spec.source);

  return (
    <div className={`spec-row ${open ? 'spec-row--open' : ''}`}>
      <button
        className="spec-row__main"
        onClick={() => hasCitation && setOpen((v) => !v)}
        aria-expanded={open}
        disabled={!hasCitation}
      >
        <span className="spec-row__attribute">{spec.attribute.replaceAll('_', ' ')}</span>
        <span className="spec-row__value">
          {spec.value}
          {spec.unit ? ` ${spec.unit}` : ''}
        </span>
        <span className="spec-row__confidence">
          <span
            className="spec-row__confidence-fill"
            style={{ width: `${Math.round(spec.confidence * 100)}%` }}
          />
        </span>
        <span className="spec-row__confidence-label">{(spec.confidence * 100).toFixed(0)}%</span>
        <StampBadge variant={statusToVariant(spec.status)} />
        {hasCitation && (
          <span className="spec-row__toggle" aria-hidden="true">
            {open ? '\u2212' : '+'}
          </span>
        )}
      </button>
      {open && hasCitation && (
        <div className="spec-row__citation">
          <p className="spec-row__citation-label">
            {resolvedSource ? (
              <>
                Source: {resolvedSource.type} &middot; {resolvedSource.reference}
                {typeof resolvedSource.page === 'number' ? ` \u00b7 p.${resolvedSource.page}` : ''}
              </>
            ) : (
              <>Source reference: {spec.source.reference} (unresolved)</>
            )}
          </p>
          {spec.source.snippet && <p className="spec-row__citation-snippet">&ldquo;{spec.source.snippet}&rdquo;</p>}
        </div>
      )}
    </div>
  );
}
