import { useEffect, useState } from 'react';
import CommerceOutput from './components/CommerceOutput';
import ExampleTags from './components/ExampleTags';
import Hero from './components/Hero';
import RawSourcePanel from './components/RawSourcePanel';
import VerifiedRecord from './components/VerifiedRecord';

export default function App() {
  const [index, setIndex] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [example, setExample] = useState(null);
  const [error, setError] = useState(null);

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

  if (error) {
    return (
      <div className="app">
        <div className="error">Couldn't load demo data: {error}</div>
      </div>
    );
  }

  if (!index || !example) {
    return (
      <div className="app">
        <div className="loading">Loading inspection report&hellip;</div>
      </div>
    );
  }

  return (
    <div className="app">
      <Hero overallConfidence={example.product_record.validation?.overall_confidence} />
      <ExampleTags examples={index} selectedId={selectedId} onSelect={setSelectedId} />
      <RawSourcePanel label={example.raw_input.label} text={example.raw_input.text} />
      <VerifiedRecord record={example.product_record} />
      <CommerceOutput commerce={example.commerce} />
    </div>
  );
}
