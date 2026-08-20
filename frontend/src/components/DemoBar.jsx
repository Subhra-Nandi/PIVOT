const KIND_LABEL = {
  catalog: 'Catalog Row',
  document: 'PDF Extraction',
  merged: 'Multi-Source',
};

export default function DemoBar({ examples, selectedId, onSelect }) {
  return (
    <nav
      aria-label="Demo presets"
      className="inline-flex w-full flex-wrap gap-1 rounded-xl border border-zinc-800 bg-zinc-900 p-1 sm:w-auto"
    >
      {examples.map((example) => {
        const active = example.example_id === selectedId;
        return (
          <button
            key={example.example_id}
            type="button"
            onClick={() => onSelect(example.example_id)}
            aria-pressed={active}
            className={`rounded-lg px-4 py-2 font-mono text-xs font-medium transition-all duration-200 ${
              active
                ? 'bg-zinc-800 text-lime-400 shadow-[0_0_0_1px_rgba(163,230,53,0.25)]'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {KIND_LABEL[example.source_kind] ?? example.source_kind}
            <span className="ml-2 hidden text-zinc-500 sm:inline">&middot; {example.title}</span>
          </button>
        );
      })}
    </nav>
  );
}
