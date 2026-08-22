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
  const [baseExample, setBaseExample] = useState(null);
  const [overridesByExample, setOverridesByExample] = useState({});
  const [statusFilter, setStatusFilter] = useState(null); // null | 'extracted' | 'inferred' | 'needs_review'
  const [activeSnippet, setActiveSnippet] = useState(null);

  // Live Extraction State
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  // Fold accepted conflict resolutions onto the live extraction result.
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

      setBaseExample(formattedData);
      setStatusFilter(null);
      setActiveSnippet(null);
    } catch (err) {
      console.error('File extraction error:', err);
      setUploadError(err.message || 'Failed to extract file from API');
    } finally {
      setIsUploading(false);
    }
  }

  const record = example?.product_record ?? null;
  const specs = record?.specifications ?? [];
  const counts = record ? summarizeSpecs(specs, record.validation?.conflicts ?? []) : null;

  return (
    <div className="min-h-screen bg-zinc-950 text-white font-sans">
      {record && <TrustHud
          overallConfidence={record.validation?.overall_confidence}
          counts={counts}
          activeFilter={statusFilter}
          onFilterChange={setStatusFilter}
        />}

      <main className="mx-auto max-w-6xl px-4 pb-24 pt-6 sm:px-6 lg:px-8">
        <MultiSourceCompare apiBaseUrl={API_BASE_URL} />
        {/* Live Upload Box */}
        <div className="mt-6 rounded-xl border border-dashed border-zinc-800 bg-zinc-900/40 p-4 transition-colors hover:border-lime-400/50">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-left">
              <p className="font-mono text-sm font-medium text-zinc-200">
                ⚡ Live Backend File Extraction
              </p>
              <p className="font-mono text-xs text-zinc-400">
                Upload a product datasheet or supplier catalog — PDF, DOCX, CSV, XLSX.
              </p>
            </div>

            <div>
              <label
                htmlFor="live-file-upload"
                className={`inline-flex cursor-pointer items-center justify-center rounded-lg bg-lime-400 px-4 py-2 font-mono text-xs font-semibold text-zinc-950 shadow transition-all hover:bg-lime-300 ${
                  isUploading ? 'opacity-50 pointer-events-none' : ''
                }`}
              >
                {isUploading ? 'Extracting via API (this can take up to a minute)...' : 'Upload & Extract File'}
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

          {uploadError && (
            <div className="mt-3 font-mono text-xs text-rose-400">
              Error: {uploadError}
            </div>
          )}
        </div>

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
                  onClick={() => setBaseExample({ ...example, product_record: item.product_record, commerce: item.commerce })}
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
      </main>
    </div>
  );
}
