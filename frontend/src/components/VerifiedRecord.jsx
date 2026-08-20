import ConflictDiffCard from './ConflictDiffCard';
import SpecRow from './SpecRow';

export default function VerifiedRecord({ record, statusFilter, onSnippetHover, onResolveConflict }) {
  const sourcesUsed = record.provenance?.sources_used ?? [];
  const resolveSource = (spec) =>
    spec.source ? sourcesUsed.find((s) => s.id === spec.source.reference) : undefined;

  const specs = record.specifications ?? [];
  const visibleSpecs = statusFilter ? specs.filter((s) => s.status === statusFilter) : specs;

  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 backdrop-blur-md">
      <div className="mb-3 flex items-baseline gap-2">
        <span className="font-mono text-xs text-zinc-600">02</span>
        <h2 className="font-display text-sm font-semibold text-zinc-100">Verified record</h2>
      </div>
      <p className="mb-3 font-mono text-[11px] text-zinc-500">
        {record.product_name}
        {record.brand ? ` \u00b7 ${record.brand}` : ''}
      </p>

      <ConflictDiffCard
        conflicts={record.validation?.conflicts}
        sourcesUsed={sourcesUsed}
        onResolve={onResolveConflict}
      />

      <div className="space-y-2">
        {visibleSpecs.length === 0 ? (
          <p className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-4 py-6 text-center font-mono text-xs text-zinc-500">
            {specs.length === 0 ? 'No specifications extracted.' : 'No specs match this filter.'}
          </p>
        ) : (
          visibleSpecs.map((spec, i) => (
            <SpecRow
              key={`${spec.attribute}-${i}`}
              spec={spec}
              resolvedSource={resolveSource(spec)}
              onSnippetHover={onSnippetHover}
            />
          ))
        )}
      </div>
    </section>
  );
}
