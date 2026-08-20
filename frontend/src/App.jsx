import { useEffect, useState } from 'react';
import CommerceOutput from './components/CommerceOutput';
import DemoBar from './components/DemoBar';
import RawSourcePanel from './components/RawSourcePanel';
import TrustHUD from './components/TrustHUD';
import VerifiedRecord from './components/VerifiedRecord';

export default function App() {
  const [index, setIndex] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [example, setExample] = useState(null);
  const [error, setError] = useState(null);

  // A local, mutable copy of the record for this example. Conflict
  // resolution (feature: "Resolve & Override") edits this copy only — the
  // original fixture and the Phase 6 commerce mappings (computed
  // server-side, at generation time) are never touched, so re-selecting
  // the example resets it cleanly.
  const [activeRecord, setActiveRecord] = useState(null);
  const [statusFilter, setStatusFilter] = useState(null);
  const [highlightSnippet, setHighlightSnippet] = useState(null);

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
    fetch(`/demo-data/${entry.file}`)
      .then((r) => {
        if (!r.ok) throw new Error(`${entry.file}: ${r.status}`);
        return r.json();
      })
      .then(setExample)
      .catch((e) => setError(e.message));
  }, [index, selectedId]);

  // Reset per-example UI state whenever a new example loads — otherwise a
  // filter or override from one example would leak into the next.
  useEffect(() => {
    if (!example) return;
    setActiveRecord(example.product_record);
    setStatusFilter(null);
    setHighlightSnippet(null);
  }, [example]);

  function resolveConflict(attribute, chosenValue, chosenSourceId) {
    setActiveRecord((prev) => {
      let kept = false;
      const specifications = [];
      for (const spec of prev.specifications) {
        if (spec.attribute !== attribute) {
          specifications.push(spec);
          continue;
        }
        const isChosen = spec.value === chosenValue && spec.source?.reference === chosenSourceId;
        if (isChosen && !kept) {
          specifications.push({ ...spec, status: 'extracted' });
          kept = true;
        }
        // Any other spec for this attribute (the losing side, or a
        // duplicate) is dropped — the conflict is resolved, not just hidden.
      }
      const conflicts = (prev.validation?.conflicts ?? []).filter((c) => c.attribute !== attribute);
      const overall_confidence = specifications.length
        ? Math.round((specifications.reduce((sum, s) => sum + s.confidence, 0) / specifications.length) * 100) / 100
        : 0;
      return {
        ...prev,
        specifications,
        validation: { ...prev.validation, conflicts, overall_confidence },
      };
    });
  }

  if (error) {
    return (
      <div className="app">
        <div className="error">Couldn't load demo data: {error}</div>
      </div>
    );
  }

  if (!index || !example || !activeRecord) {
    return (
      <div className="app">
        <div className="loading">Loading inspection report&hellip;</div>
      </div>
    );
  }

  const sourcesUsed = activeRecord.provenance?.sources_used ?? [];

  return (
    <div className="app">
      <TrustHUD record={activeRecord} statusFilter={statusFilter} onFilterChange={setStatusFilter} />
      <DemoBar examples={index} selectedId={selectedId} onSelect={setSelectedId} />

      <div className="split-screen">
        <div className="split-screen__source">
          <RawSourcePanel label={example.raw_input.label} text={example.raw_input.text} highlightSnippet={highlightSnippet} />
        </div>
        <div className="split-screen__record">
          <VerifiedRecord
            record={activeRecord}
            sourcesUsed={sourcesUsed}
            statusFilter={statusFilter}
            onHighlight={setHighlightSnippet}
            onResolveConflict={resolveConflict}
          />
        </div>
      </div>

      <CommerceOutput commerce={example.commerce} />
    </div>
  );
}
