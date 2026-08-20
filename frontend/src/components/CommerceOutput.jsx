import { useState } from 'react';

const FORMATS = [
  { key: 'schema_org', label: 'Schema.org' },
  { key: 'google_shopping', label: 'Google Shopping' },
  { key: 'industrial', label: 'ETIM-style' },
];

function issueSeverity(issue) {
  if (issue.startsWith('required:')) return 'required';
  if (issue.startsWith('recommended:')) return 'recommended';
  return 'warning';
}

const ISSUE_CLASSES = {
  required: 'border-rose-500/30 bg-rose-500/[0.06] text-rose-300',
  recommended: 'border-amber-500/30 bg-amber-500/[0.06] text-amber-300',
  warning: 'border-amber-500/30 bg-amber-500/[0.06] text-amber-300',
};

function IssuesDrawer({ issues }) {
  if (issues.length === 0) {
    return (
      <p className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/[0.06] px-3 py-2 font-mono text-xs text-emerald-400">
        No validation issues.
      </p>
    );
  }
  return (
    <ul className="mt-3 space-y-1.5">
      {issues.map((issue, i) => {
        const severity = issueSeverity(issue);
        return (
          <li
            key={i}
            className={`flex items-start gap-2 rounded-lg border px-3 py-1.5 font-mono text-[11px] ${ISSUE_CLASSES[severity]}`}
          >
            <span aria-hidden="true">&#9888;</span>
            <span>{issue}</span>
          </li>
        );
      })}
    </ul>
  );
}

function GoogleShoppingCard({ doc }) {
  const missingImage = !doc.image_link;
  return (
    <div className="mx-auto max-w-xs rounded-xl border border-zinc-800 bg-zinc-950 p-3">
      <div className="relative flex aspect-square items-center justify-center rounded-lg border border-dashed border-zinc-700 bg-zinc-900">
        {doc.image_link ? (
          <img src={doc.image_link} alt="" className="h-full w-full rounded-lg object-cover" />
        ) : (
          <span className="font-mono text-[10px] text-zinc-600">no image_link</span>
        )}
        {missingImage && (
          <span className="absolute right-1.5 top-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 font-mono text-[9px] text-amber-400">
            missing image
          </span>
        )}
      </div>
      <p className="mt-2 truncate text-sm font-medium text-zinc-100">{doc.title}</p>
      <p className="truncate font-mono text-[11px] text-zinc-500">{doc.brand ?? '—'}</p>
      <div className="mt-1.5 flex items-center justify-between">
        {doc.price ? (
          <span className="font-mono text-sm font-semibold text-zinc-100">{doc.price}</span>
        ) : (
          <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] text-amber-400">
            missing offer
          </span>
        )}
        {doc.availability && (
          <span className="font-mono text-[10px] text-zinc-500">{doc.availability}</span>
        )}
      </div>
    </div>
  );
}

function IndustrialSheet({ doc }) {
  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800">
      <div className="border-b border-zinc-800 bg-zinc-900 px-4 py-2">
        <p className="font-mono text-xs text-zinc-300">
          {doc.class_name || 'Unclassified'}
          {doc.class_code ? ` (${doc.class_code})` : ''}
        </p>
      </div>
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-950 font-mono text-[10px] uppercase tracking-wide text-zinc-500">
            <th className="px-4 py-2 font-medium">Feature</th>
            <th className="px-4 py-2 font-medium">Value</th>
            <th className="px-4 py-2 font-medium">Unit</th>
          </tr>
        </thead>
        <tbody>
          {(doc.features ?? []).map((f, i) => (
            <tr key={i} className="border-b border-zinc-800/60 last:border-0">
              <td className="px-4 py-2 font-mono text-xs text-zinc-400">
                {f.feature_name.replaceAll('_', ' ')}
              </td>
              <td className="px-4 py-2 font-mono text-xs text-zinc-100">{f.value}</td>
              <td className="px-4 py-2 font-mono text-xs text-zinc-500">{f.unit ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SchemaOrgCard({ doc }) {
  const offers = doc.offers;
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <p className="text-sm font-medium text-zinc-100">{doc.name}</p>
      <p className="font-mono text-[11px] text-zinc-500">{doc.brand?.name ?? '—'}</p>
      <div className="mt-2 flex items-center gap-2">
        {offers?.price ? (
          <span className="font-mono text-sm font-semibold text-zinc-100">
            {offers.price} {offers.priceCurrency}
          </span>
        ) : (
          <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] text-amber-400">
            missing offers
          </span>
        )}
      </div>
      {doc.additionalProperty?.length > 0 && (
        <div className="mt-3 space-y-1 border-t border-zinc-800 pt-3">
          {doc.additionalProperty.map((p, i) => (
            <div key={i} className="flex justify-between font-mono text-[11px]">
              <span className="text-zinc-500">{p.name.replaceAll('_', ' ')}</span>
              <span className="text-zinc-300">
                {p.value}
                {p.unitCode ? ` ${p.unitCode}` : p.unitText ? ` ${p.unitText}` : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CommerceOutput({ commerce }) {
  const [format, setFormat] = useState('schema_org');
  const [view, setView] = useState('code'); // 'code' | 'visual'
  const current = commerce[format];

  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 backdrop-blur-md">
      <div className="mb-3 flex items-baseline gap-2">
        <span className="font-mono text-xs text-zinc-600">03</span>
        <h2 className="font-display text-sm font-semibold text-zinc-100">Commerce output</h2>
      </div>
      <p className="mb-4 font-mono text-[11px] text-zinc-500">
        Mapped to a recognized standard, then validated against it.
      </p>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex gap-1 rounded-xl border border-zinc-800 bg-zinc-900 p-1">
          {FORMATS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFormat(f.key)}
              aria-pressed={f.key === format}
              className={`rounded-lg px-3 py-1.5 font-mono text-xs font-medium transition-all duration-200 ${
                f.key === format
                  ? 'bg-zinc-800 text-lime-400 shadow-[0_0_0_1px_rgba(163,230,53,0.25)]'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="inline-flex gap-1 rounded-xl border border-zinc-800 bg-zinc-900 p-1">
          {[
            { key: 'code', label: 'Code' },
            { key: 'visual', label: 'Visual' },
          ].map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => setView(v.key)}
              aria-pressed={view === v.key}
              className={`rounded-lg px-3 py-1.5 font-mono text-xs font-medium transition-all duration-200 ${
                view === v.key
                  ? 'bg-zinc-800 text-violet-400 shadow-[0_0_0_1px_rgba(139,92,246,0.25)]'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4">
        {view === 'code' ? (
          <pre className="thin-scroll max-h-96 overflow-auto rounded-xl border border-zinc-800/80 bg-zinc-950 p-4 font-mono text-xs leading-relaxed text-zinc-300">
            {JSON.stringify(current.document, null, 2)}
          </pre>
        ) : format === 'google_shopping' ? (
          <GoogleShoppingCard doc={current.document} />
        ) : format === 'industrial' ? (
          <IndustrialSheet doc={current.document} />
        ) : (
          <SchemaOrgCard doc={current.document} />
        )}
      </div>

      <IssuesDrawer issues={current.issues} />
    </section>
  );
}
