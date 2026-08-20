import './DemoBar.css';

const KIND_LABEL = {
  catalog: 'Catalog row',
  document: 'PDF extraction',
  merged: 'Multi-source',
};

/** Feature: "1-Click Demo" sample bar — a judge with two minutes shouldn't
 * have to upload anything. Every sample here already ran through the full
 * ingestion-to-export pipeline; picking one just swaps which result is on
 * screen. */
export default function DemoBar({ examples, selectedId, onSelect }) {
  return (
    <nav className="demo-bar" aria-label="1-click demo samples">
      <span className="demo-bar__label">1-Click Demo</span>
      <div className="demo-bar__tags">
        {examples.map((example) => (
          <button
            key={example.example_id}
            className={`tag ${example.example_id === selectedId ? 'tag--active' : ''}`}
            onClick={() => onSelect(example.example_id)}
            aria-pressed={example.example_id === selectedId}
          >
            <span className="tag__hole" aria-hidden="true" />
            <span className="tag__kind">{KIND_LABEL[example.source_kind] ?? example.source_kind}</span>
            <span className="tag__title">Try: {example.title}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
