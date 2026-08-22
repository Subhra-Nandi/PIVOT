import { useState } from 'react';
import { summarizeSpecs } from '../lib/specClassification';

export default function MultiSourceCompare({ apiBaseUrl }) {
  const [files, setFiles] = useState([null, null]);
  const [result, setResult] = useState(null);
  const [indices, setIndices] = useState([0, 0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function compare() {
    if (!files[0] || !files[1]) return;
    setBusy(true); setError(null);
    const form = new FormData();
    form.append('source_a', files[0]); form.append('source_b', files[1]);
    if (result?.requires_selection) { form.append('source_a_index', indices[0]); form.append('source_b_index', indices[1]); }
    try {
      const response = await fetch(`${apiBaseUrl}/compare/files`, { method: 'POST', body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || `Comparison failed (${response.status})`);
      setResult(body);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  const record = result?.product_record;
  const sources = result?.source_records || [];
  const rows = (() => {
    if (!record) return [];
    const attrs = new Set(record.specifications?.map((s) => s.attribute));
    sources.forEach(({ product_record: r }) => r.specifications?.forEach((s) => attrs.add(s.attribute)));
    return [...attrs].map((attribute) => ({ attribute, values: sources.map(({ product_record: r }) => r.specifications?.filter((s) => s.attribute === attribute) || []), conflict: record.validation?.conflicts?.some((c) => c.attribute === attribute) }));
  })();
  const counts = record ? summarizeSpecs(record.specifications, record.validation?.conflicts) : null;

  return <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
    <div className="mb-4"><p className="font-mono text-xs text-lime-300">MULTI-SOURCE COMPARISON</p><h2 className="font-display text-lg">Compare two product sources</h2></div>
    <div className="grid gap-3 sm:grid-cols-2">
      {files.map((file, i) => <label key={i} className="rounded-xl border border-dashed border-zinc-700 p-4 font-mono text-xs text-zinc-400">Source {String.fromCharCode(65 + i)}<input type="file" accept=".pdf,.docx,.csv,.xlsx,.xlsm" className="mt-2 block w-full text-xs" onChange={(e) => { const next = [...files]; next[i] = e.target.files?.[0] || null; setFiles(next); setResult(null); }} />{file && <span className="mt-2 block text-zinc-200">{file.name}</span>}</label>)}
    </div>
    {result?.requires_selection && <div className="mt-4 grid gap-3 sm:grid-cols-2">{result.sources.map((source, i) => <label key={source.filename} className="font-mono text-xs text-zinc-400">Select Source {String.fromCharCode(65 + i)}<select className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 p-2 text-zinc-200" value={indices[i]} onChange={(e) => { const next = [...indices]; next[i] = Number(e.target.value); setIndices(next); }}>{source.items.map((item, j) => <option key={j} value={j}>{item.product_name}</option>)}</select></label>)}</div>}
    <button type="button" disabled={busy || !files[0] || !files[1]} onClick={compare} className="mt-4 rounded-lg bg-lime-400 px-4 py-2 font-mono text-xs font-semibold text-zinc-950 disabled:opacity-40">{busy ? 'Comparing…' : result?.requires_selection ? 'Compare selected products' : 'Compare Sources'}</button>
    {error && <p className="mt-3 font-mono text-xs text-rose-400">{error}</p>}
    {record && <><div className="mt-5 flex flex-wrap gap-3 font-mono text-xs"><span className="text-lime-300">{counts.grounded} Agreements</span><span className="text-amber-300">{counts.unverified} Unverified</span><span className="text-rose-300">{counts.conflict} Conflicts</span></div><div className="mt-3 overflow-x-auto"><table className="w-full text-left font-mono text-xs"><thead><tr className="border-b border-zinc-800 text-zinc-500"><th className="p-2">Attribute</th><th className="p-2">{sources[0]?.filename || 'Source A'}</th><th className="p-2">{sources[1]?.filename || 'Source B'}</th><th className="p-2">Result</th></tr></thead><tbody>{rows.map((row) => <tr key={row.attribute} className="border-b border-zinc-900"><td className="p-2 text-zinc-300">{row.attribute}</td>{row.values.map((values, i) => <td key={i} className="p-2 text-zinc-200">{values.length ? values.map((s) => `${s.value}${s.unit ? ` ${s.unit}` : ''}`).join(', ') : '—'}</td>)}<td className={`p-2 font-semibold ${row.conflict ? 'text-rose-300' : 'text-lime-300'}`}>{row.conflict ? 'CONFLICT' : (row.values.some((v) => v.length) ? 'AGREEMENT / VERIFIED' : 'UNVERIFIED')}</td></tr>)}</tbody></table></div></>}
  </section>;
}
