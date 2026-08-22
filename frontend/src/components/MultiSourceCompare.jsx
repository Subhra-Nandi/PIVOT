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

  return <section className="mt-7 rounded-2xl border border-zinc-800 bg-zinc-900/45 p-5 sm:p-6">
    <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between"><div><p className="font-mono text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">Optional workflow</p><h2 className="mt-1 font-display text-xl font-semibold text-zinc-100">Compare two sources</h2><p className="mt-1 text-sm text-zinc-400">Check supplier and manufacturer data for agreement or conflicts.</p></div><span className="font-mono text-[11px] text-zinc-600">Backend-verified comparison</span></div>
    <div className="grid gap-3 sm:grid-cols-2">
      {files.map((file, i) => <div key={i} className="rounded-xl border border-dashed border-zinc-700 bg-zinc-950/45 p-4"><p className="font-mono text-xs font-medium text-zinc-300">Source {String.fromCharCode(65 + i)}</p><p className="mt-1 truncate font-mono text-[11px] text-zinc-500">{file ? file.name : 'No file selected'}</p><label htmlFor={`compare-file-${i}`} className="mt-4 inline-flex cursor-pointer rounded-md border border-zinc-700 px-3 py-2 font-mono text-[11px] font-medium text-zinc-200 transition hover:border-lime-400/70 hover:text-lime-300">{file ? 'Replace file' : 'Choose file'}</label><input id={`compare-file-${i}`} type="file" accept=".pdf,.docx,.csv,.xlsx,.xlsm" className="sr-only" onChange={(e) => { const next = [...files]; next[i] = e.target.files?.[0] || null; setFiles(next); setResult(null); }} /></div>)}
    </div>
    {result?.requires_selection && <div className="mt-4 grid gap-3 sm:grid-cols-2">{result.sources.map((source, i) => <label key={source.filename} className="font-mono text-xs text-zinc-400">Select Source {String.fromCharCode(65 + i)}<select className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 p-2 text-zinc-200" value={indices[i]} onChange={(e) => { const next = [...indices]; next[i] = Number(e.target.value); setIndices(next); }}>{source.items.map((item, j) => <option key={j} value={j}>{item.product_name}</option>)}</select></label>)}</div>}
    <button type="button" disabled={busy || !files[0] || !files[1]} onClick={compare} className="mt-5 rounded-lg border border-lime-400/60 px-4 py-2.5 font-mono text-xs font-semibold text-lime-300 transition hover:bg-lime-400 hover:text-zinc-950 disabled:cursor-not-allowed disabled:border-zinc-700 disabled:text-zinc-600">{busy ? 'Comparing…' : result?.requires_selection ? 'Compare selected products' : 'Compare sources'}</button>
    {error && <p className="mt-3 font-mono text-xs text-rose-400">{error}</p>}
    {record && <><div className="mt-5 flex flex-wrap gap-3 font-mono text-xs"><span className="text-lime-300">{counts.grounded} Agreements</span><span className="text-amber-300">{counts.unverified} Unverified</span><span className="text-rose-300">{counts.conflict} Conflicts</span></div><div className="mt-3 overflow-x-auto"><table className="w-full text-left font-mono text-xs"><thead><tr className="border-b border-zinc-800 text-zinc-500"><th className="p-2">Attribute</th><th className="p-2">{sources[0]?.filename || 'Source A'}</th><th className="p-2">{sources[1]?.filename || 'Source B'}</th><th className="p-2">Result</th></tr></thead><tbody>{rows.map((row) => <tr key={row.attribute} className="border-b border-zinc-900"><td className="p-2 text-zinc-300">{row.attribute}</td>{row.values.map((values, i) => <td key={i} className="p-2 text-zinc-200">{values.length ? values.map((s) => `${s.value}${s.unit ? ` ${s.unit}` : ''}`).join(', ') : '—'}</td>)}<td className={`p-2 font-semibold ${row.conflict ? 'text-rose-300' : 'text-lime-300'}`}>{row.conflict ? 'CONFLICT' : (row.values.some((v) => v.length) ? 'AGREEMENT / VERIFIED' : 'UNVERIFIED')}</td></tr>)}</tbody></table></div></>}
  </section>;
}
