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

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Minimal, dependency-free JSON syntax highlighter — colors keys, strings,
 * numbers, and booleans/null so the "code card" reads like a code editor
 * without pulling in a highlighting library for one static view. */
function highlightJson(json) {
  const escaped = escapeHtml(json);
  return escaped.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let cls = 'json-number';
      if (match.startsWith('"')) {
        cls = /:$/.test(match) ? 'json-key' : 'json-string';
      } else if (match === 'true' || match === 'false') {
        cls = 'json-boolean';
      } else if (match === 'null') {
        cls = 'json-null';
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="copy-btn"
      onClick={() => {
        navigator.clipboard?.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

function CodeCard({ document }) {
  const json = JSON.stringify(document, null, 2);
  return (
    <div className="code-card">
      <CopyButton text={json} />
      <pre className="scan-strip commerce-json" dangerouslySetInnerHTML={{ __html: highlightJson(json) }} />
    </div>
  );
}

function GoogleShoppingCard({ doc }) {
  return (
    <div className="mock-gcard">
      <div className="mock-gcard__image">
        {doc.image_link ? <img src={doc.image_link} alt="" /> : <span className="mock-gcard__placeholder">No image</span>}
      </div>
      <div className="mock-gcard__body">
        <p className="mock-gcard__title">{doc.title ?? 'Untitled product'}</p>
        {doc.price && <p className="mock-gcard__price">{doc.price}</p>}
        {doc.availability && <span className="mock-gcard__availability">{doc.availability}</span>}
        {doc.brand && <p className="mock-gcard__brand">{doc.brand}</p>}
        {doc.description && <p className="mock-gcard__description">{doc.description}</p>}
      </div>
    </div>
  );
}

function RichResultPreview({ doc }) {
  const price = doc.offers?.price;
  const currency = doc.offers?.priceCurrency ?? '';
  return (
    <div className="mock-rich-result">
      <p className="mock-rich-result__eyebrow">Google Rich Result &mdash; preview</p>
      <div className="mock-rich-result__card">
        <div className="mock-rich-result__image">
          {doc.image?.[0] ? <img src={doc.image[0]} alt="" /> : <span className="mock-gcard__placeholder">No image</span>}
        </div>
        <div className="mock-rich-result__body">
          <p className="mock-rich-result__title">{doc.name}</p>
          {doc.brand?.name && <p className="mock-rich-result__brand">{doc.brand.name}</p>}
          {price != null && (
            <p className="mock-rich-result__price">
              {currency} {price}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function EtimSheet({ doc }) {
  return (
    <div className="etim-sheet">
      <div className="etim-sheet__header">
        <span className="etim-sheet__class">{doc.class_name ?? 'Unclassified'}</span>
        {doc.brand && <span className="etim-sheet__brand">{doc.brand}</span>}
      </div>
      <table className="etim-sheet__table">
        <thead>
          <tr>
            <th>Feature</th>
            <th>Value</th>
            <th>Unit</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {(doc.features ?? []).map((f, i) => (
            <tr key={i}>
              <td>{f.feature_name.replaceAll('_', ' ')}</td>
              <td>{String(f.value)}</td>
              <td>{f.unit ?? '\u2014'}</td>
              <td>{Math.round((f.confidence ?? 0) * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="etim-sheet__note">{doc.classification_note}</p>
    </div>
  );
}

const PREVIEWS = {
  schema_org: RichResultPreview,
  google_shopping: GoogleShoppingCard,
  industrial: EtimSheet,
};

export default function CommerceOutput({ commerce }) {
  const [format, setFormat] = useState('schema_org');
  const [view, setView] = useState('preview');
  const current = commerce[format];
  const Preview = PREVIEWS[format];

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
        <div className="view-toggle">
          <button className={view === 'preview' ? 'view-toggle__btn view-toggle__btn--active' : 'view-toggle__btn'} onClick={() => setView('preview')}>
            Preview
          </button>
          <button className={view === 'code' ? 'view-toggle__btn view-toggle__btn--active' : 'view-toggle__btn'} onClick={() => setView('code')}>
            Code
          </button>
        </div>
      </div>

      {view === 'preview' ? (
        <Preview doc={current.document} />
      ) : (
        <CodeCard document={current.document} />
      )}

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
