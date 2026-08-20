import { useState } from 'react';
import StampBadge, { statusToVariant } from './StampBadge';
import './SpecRow.css';

export default function SpecRow({ spec, resolvedSource, onHighlight }) {
  const [open, setOpen] = useState(false);
  const hasCitation = Boolean(spec.source);
  // Some values already embed their unit as text (e.g. an LLM emitting
  // "5V" for both `value` and `unit: "V"`) — only append the separate
  // unit field when the value doesn't already end with it, so the row
  // doesn't render "5V V".
  const showUnit = spec.unit && !String(spec.value).toLowerCase().endsWith(String(spec.unit).toLowerCase());

  function toggle() {
    if (!hasCitation) return;
    const next = !open;
    setOpen(next);
    if (next && spec.source.snippet) onHighlight?.(spec.source.snippet);
  }

  return (
    <div className={`spec-row ${open ? 'spec-row--open' : ''}`}>
      <button className="spec-row__main" onClick={toggle} aria-expanded={open} disabled={!hasCitation}>
        <span className="spec-row__attribute">{spec.attribute.replaceAll('_', ' ')}</span>
        <span className="spec-row__value">
          {spec.value}
          {showUnit ? ` ${spec.unit}` : ''}
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
          {spec.source.snippet && (
            <>
              <p className="spec-row__citation-snippet">&ldquo;{spec.source.snippet}&rdquo;</p>
              <button
                className="spec-row__locate"
                onClick={(e) => {
                  e.stopPropagation();
                  onHighlight?.(spec.source.snippet);
                }}
              >
                Locate in source &rarr;
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
