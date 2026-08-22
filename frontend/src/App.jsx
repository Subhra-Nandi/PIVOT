import { useMemo, useState } from 'react';
import TrustHud from './components/TrustHud';
import SourceInspector from './components/SourceInspector';
import VerifiedRecord from './components/VerifiedRecord';
import CommerceOutput from './components/CommerceOutput';
import { resolveConflict } from './lib/resolveConflict';
import { summarizeSpecs } from './lib/specClassification';
import MultiSourceCompare from './components/MultiSourceCompare';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://pivot-backend-8ydb.onrender.com';

export default function App() {
  const [uploadResult, setUploadResult] = useState(null);
  const [overridesByExample, setOverridesByExample] = useState({});
  const [statusFilter, setStatusFilter] = useState(null); // null | 'extracted' | 'inferred' | 'needs_review'
  const [activeSnippet, setActiveSnippet] = useState(null);

  // Live Extraction State
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [isDragActive, setIsDragActive] = useState(false);

  // Fold accepted conflict resolutions onto the live extraction result.
  const example = useMemo(() => {
    if (!uploadResult) return null;
    const overrides = overridesByExample[uploadResult.example_id] ?? {};
    return Object.entries(overrides).reduce(
      (acc, [attribute, acceptedIndex]) => resolveConflict(acc, attribute, acceptedIndex),
      uploadResult
    );
  }, [uploadResult, overridesByExample]);

  function handleResolveConflict(attribute, acceptedIndex) {
    if (!uploadResult) return;
    setOverridesByExample((prev) => ({
      ...prev,
      [uploadResult.example_id]: {
        ...prev[uploadResult.example_id],
        [attribute]: acceptedIndex,
      },
    }));
  }

  // 4. Handle Live File Upload to Render FastAPI Endpoint
  async function handleFileUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE_URL}/extract/file`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let detail = `Backend request failed with status ${response.status}`;
        try {
          const body = await response.json();
          const structured = body.detail;
          detail = typeof structured === 'object'
            ? `${structured.message || 'Catalog could not be processed'}${structured.detected_headers?.length ? ` Detected columns: ${structured.detected_headers.join(', ')}` : ''}`
            : (structured || body.message || detail);
        } catch { /* non-JSON response */ }
        throw new Error(detail);
      }

      const liveData = await response.json();

      const sourceText = liveData.source?.blocks?.map((block) => {
        const location = block.page ? `Page ${block.page}` : (block.section || 'Source');
        return `${location}\n${block.text}`;
      }).join('\n\n') || '';

      const formattedData = {
       example_id: `custom_${Date.now()}`,
       raw_input: {
        label: `Live upload: ${file.name}`,
        text: liveData.items
         ? `${liveData.total_rows} row(s) parsed from ${file.name}. Row warnings: ${liveData.row_warnings?.length || 0}.`
         : sourceText || `Extracted from ${file.name} via live pipeline — source text unavailable.`,
},
  ...liveData,
};

      setUploadResult(formattedData);
      setStatusFilter(null);
      setActiveSnippet(null);
    } catch (err) {
      console.error('File extraction error:', err);
      setUploadError(err.message || 'Failed to extract file from API');
    } finally {
      setIsUploading(false);
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    setIsDragActive(false);
    const [file] = event.dataTransfer.files;
    if (file) handleFileUpload({ target: { files: [file] } });
  }

  const record = example?.product_record ?? null;
  const specs = record?.specifications ?? [];
  const counts = record
    ? summarizeSpecs(specs, record.validation?.conflicts ?? [])
    : { grounded: 0, unverified: 0, conflict: 0 };

  return (
    <div className="min-h-screen bg-zinc-950 text-white font-sans">
      <TrustHud
          overallConfidence={record?.validation?.overall_confidence}
          counts={counts}
          activeFilter={statusFilter}
          onFilterChange={setStatusFilter}
        />

      <main className="mx-auto max-w-6xl px-4 pb-24 pt-8 sm:px-6 lg:px-8">
        <section className="mb-7 max-w-2xl">
          <p className="font-mono text-xs font-medium uppercase tracking-[0.18em] text-lime-300">Product data workspace</p>
          <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-zinc-100 sm:text-3xl">Turn messy product data into trusted, commerce-ready records.</h2>
          <p className="mt-3 font-mono text-xs text-zinc-500">PDF · DOCX · CSV · XLSX</p>
        </section>

        <section
          className={`rounded-2xl border bg-zinc-900/70 p-5 shadow-xl transition-colors sm:p-7 ${isDragActive ? 'border-lime-400 bg-lime-400/5' : 'border-zinc-800'}`}
          onDragEnter={(event) => { event.preventDefault(); setIsDragActive(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setIsDragActive(false)}
          onDrop={handleDrop}
        >
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-mono text-xs font-medium uppercase tracking-[0.16em] text-lime-300">Live backend extraction</p>
              <h3 className="mt-2 font-display text-xl font-semibold text-zinc-100">Upload a product source</h3>
              <p className="mt-1.5 max-w-xl text-sm text-zinc-400">Drag and drop a datasheet or catalog, or choose a file to extract, validate, and inspect its product record.</p>
            </div>
            <div className="shrink-0">
              <label
                htmlFor="live-file-upload"
                className={`inline-flex cursor-pointer items-center justify-center rounded-lg bg-lime-400 px-5 py-3 font-mono text-xs font-semibold text-zinc-950 shadow-glow-lime-sm transition-all hover:bg-lime-300 ${
                  isUploading ? 'opacity-50 pointer-events-none' : ''
                }`}
              >
                {isUploading ? 'Extracting…' : 'Choose file & extract'}
              </label>
              <input
                id="live-file-upload"
                type="file"
                accept=".pdf,.csv,.xlsx,.docx"
                onChange={handleFileUpload}
                className="hidden"
                disabled={isUploading}
              />
            </div>
          </div>

          <p className="mt-5 font-mono text-[11px] text-zinc-500">Drop a file anywhere in this card · PDF, DOCX, CSV, XLSX, XLSM</p>

          {uploadError && (
            <div className="mt-3 font-mono text-xs text-rose-400">
              Error: {uploadError}
            </div>
          )}
        </section>

        {record && <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <SourceInspector
              label={example.raw_input?.label || 'Source Input'}
              text={example.raw_input?.text || ''}
              activeSnippet={activeSnippet}
            />
            <VerifiedRecord
              record={record}
              statusFilter={statusFilter}
              activeSnippet={activeSnippet}
              onSnippetHover={setActiveSnippet}
              onResolveConflict={handleResolveConflict}
            />
          </div>}

        {example?.items?.length > 1 && (
          <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <div className="mb-3 font-mono text-sm text-zinc-300">{example.items.length} products detected</div>
            <div className="flex max-h-48 flex-wrap gap-2 overflow-auto">
              {example.items.map((item, itemIndex) => (
                <button key={item.product_record.product_id || itemIndex}
                  onClick={() => setUploadResult({ ...example, product_record: item.product_record, commerce: item.commerce })}
                  className="rounded-lg border border-zinc-700 px-3 py-2 text-left font-mono text-xs text-zinc-300 hover:border-lime-400 hover:text-lime-300">
                  {item.product_record.product_name || `Product ${itemIndex + 1}`}
                </button>
              ))}
            </div>
          </div>
        )}

        {record && <div className="mt-6">
            <CommerceOutput commerce={example.commerce} />
          </div>}

        <MultiSourceCompare apiBaseUrl={API_BASE_URL} />
      </main>
    </div>
  );
}
