import { useState } from 'react';
import './Panel.css';
import './CommerceOutput.css';

const FORMATS = [
  { key: 'schema_org', label: 'Schema.org' },
  { key: 'google_shopping', label: 'Google Shopping' },
  { key: 'industrial', label: 'ETIM-style' },
];

function issueSeverity(issue) {
  if (issue.startsWith('required:')) return 'required';
  if (issue.startsWith('recommended:')) return 'recommended';
  return 'warning';
}

export default function CommerceOutput({ commerce }) {
  const [format, setFormat] = useState('schema_org');
  const current = commerce[format];

  return (
    <section className="panel">
      <h2 className="panel__heading">
        <span className="panel__index">03</span> Commerce output
      </h2>
      <p className="panel__caption">Mapped to a recognized standard, then validated against it.</p>

      <div className="format-tabs">
        {FORMATS.map((f) => (
          <button
            key={f.key}
            className={`format-tab ${f.key === format ? 'format-tab--active' : ''}`}
            onClick={() => setFormat(f.key)}
            aria-pressed={f.key === format}
          >
            {f.label}
          </button>
        ))}
      </div>

      <pre className="scan-strip commerce-json">{JSON.stringify(current.document, null, 2)}</pre>

      {current.issues.length > 0 && (
        <ul className="commerce-issues">
          {current.issues.map((issue, i) => (
            <li key={i} className={`commerce-issues__item commerce-issues__item--${issueSeverity(issue)}`}>
              {issue}
            </li>
          ))}
        </ul>
      )}
      {current.issues.length === 0 && <p className="commerce-issues__clean">No validation issues.</p>}
    </section>
  );
}
