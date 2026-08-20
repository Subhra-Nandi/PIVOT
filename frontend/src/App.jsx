import { useEffect, useMemo, useState } from 'react';
import TrustHud from './components/TrustHud';
import DemoBar from './components/DemoBar';
import SourceInspector from './components/SourceInspector';
import VerifiedRecord from './components/VerifiedRecord';
import CommerceOutput from './components/CommerceOutput';
import { resolveConflict } from './lib/resolveConflict';

export default function App() {
  const [index, setIndex] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [baseExample, setBaseExample] = useState(null);
  const [error, setError] = useState(null);

  // Client-side conflict resolutions, keyed by example id then attribute.
  // Kept separate from baseExample so switching demos and back doesn't
  // lose (or leak) a resolution from a different record.
  const [overridesByExample, setOverridesByExample] = useState({});

  const [statusFilter, setStatusFilter] = useState(null); // null | 'extracted' | 'inferred' | 'needs_review'
  const [activeSnippet, setActiveSnippet] = useState(null); // citation <-> raw source sync

  useEffect(() => {
    fetch('/demo-data/index.json')
      .then((r) => {
        if (!r.ok) throw new Error(`index.json: ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setIndex(data);
        if (data.length > 0) setSelectedId(data[0].example_id);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!index || !selectedId) return;
    const entry = index.find((e) => e.example_id === selectedId);
    if (!entry) return;
    setStatusFilter(null);
    setActiveSnippet(null);
    fetch(`/demo-data/${entry.file}`)
      .then((r) => {
        if (!r.ok) throw new Error(`${entry.file}: ${r.status}`);
        return r.json();
      })
      .then(setBaseExample)
      .catch((e) => setError(e.message));
  }, [index, selectedId]);

  // Fold this example's accepted conflict resolutions (if any) onto the
  // freshly-fetched base example. resolveConflict() is pure, so re-applying
  // the whole chain on every render is cheap and can't drift from state.
  const example = useMemo(() => {
    if (!baseExample) return null;
    const overrides = overridesByExample[baseExample.example_id] ?? {};
    return Object.entries(overrides).reduce(
      (acc, [attribute, acceptedIndex]) => resolveConflict(acc, attribute, acceptedIndex),
      baseExample
    );
  }, [baseExample, overridesByExample]);

  function handleResolveConflict(attribute, acceptedIndex) {
    if (!baseExample) return;
    setOverridesByExample((prev) => ({
      ...prev,
      [baseExample.example_id]: {
        ...prev[baseExample.example_id],
        [attribute]: acceptedIndex,
      },
    }));
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 px-6">
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-6 py-4 font-mono text-sm text-rose-400">
          Couldn&rsquo;t load demo data: {error}
        </div>
      </div>
    );
  }

  if (!index || !example) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950">
        <div className="font-mono text-sm text-zinc-500">Loading inspection report&hellip;</div>
      </div>
    );
  }

  const record = example.product_record;
  const specs = record.specifications ?? [];
  const grounded = specs.filter((s) => s.status === 'extracted').length;
  const unverified = specs.filter((s) => s.status === 'inferred').length;
  const conflictCount = record.validation?.conflicts?.length ?? 0;

  return (
    <div className="min-h-screen bg-zinc-950">
      <TrustHud
        overallConfidence={record.validation?.overall_confidence}
        counts={{ grounded, unverified, conflict: conflictCount }}
        activeFilter={statusFilter}
        onFilterChange={setStatusFilter}
      />

      <main className="mx-auto max-w-6xl px-4 pb-24 pt-6 sm:px-6 lg:px-8">
        <DemoBar examples={index} selectedId={selectedId} onSelect={setSelectedId} />

        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <SourceInspector
            label={example.raw_input.label}
            text={example.raw_input.text}
            activeSnippet={activeSnippet}
          />
          <VerifiedRecord
            record={record}
            statusFilter={statusFilter}
            activeSnippet={activeSnippet}
            onSnippetHover={setActiveSnippet}
            onResolveConflict={handleResolveConflict}
          />
        </div>

        <div className="mt-6">
          <CommerceOutput commerce={example.commerce} />
        </div>
      </main>
    </div>
  );
}
