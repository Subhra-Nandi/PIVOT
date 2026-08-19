import './ExampleTags.css';

const KIND_LABEL = {
  catalog: 'Catalog row',
  document: 'PDF extraction',
  merged: 'Multi-source',
};

export default function ExampleTags({ examples, selectedId, onSelect }) {
  return (
    <nav className="tags" aria-label="Example records">
      {examples.map((example) => (
        <button
          key={example.example_id}
          className={`tag ${example.example_id === selectedId ? 'tag--active' : ''}`}
          onClick={() => onSelect(example.example_id)}
          aria-pressed={example.example_id === selectedId}
        >
          <span className="tag__hole" aria-hidden="true" />
          <span className="tag__kind">{KIND_LABEL[example.source_kind] ?? example.source_kind}</span>
          <span className="tag__title">{example.title}</span>
        </button>
      ))}
    </nav>
  );
}
