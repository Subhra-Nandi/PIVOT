import ConflictResolver from './ConflictResolver';
import SpecRow from './SpecRow';
import './Panel.css';
import './VerifiedRecord.css';

export default function VerifiedRecord({ record, sourcesUsed, statusFilter, onHighlight, onResolveConflict }) {
  const resolveSource = (spec) => (spec.source ? sourcesUsed.find((s) => s.id === spec.source.reference) : undefined);

  const conflictAttributes = new Set((record.validation?.conflicts ?? []).map((c) => c.attribute));
  const visibleSpecs = record.specifications.filter((spec) => {
    if (!statusFilter) return true;
    if (statusFilter === 'conflict') return conflictAttributes.has(spec.attribute);
    return spec.status === statusFilter;
  });

  return (
    <section className="panel">
      <h2 className="panel__heading">
        <span className="panel__index">02</span> Verified record
      </h2>
      <p className="panel__caption">
        {record.product_name}
        {record.brand ? ` \u00b7 ${record.brand}` : ''}
      </p>

      <ConflictResolver
        conflicts={record.validation?.conflicts}
        sourcesUsed={sourcesUsed}
        onResolve={onResolveConflict}
      />

      <div className="spec-table">
        {visibleSpecs.length === 0 ? (
          <p className="spec-table__empty">
            {record.specifications.length === 0 ? 'No specifications extracted.' : 'No fields match this filter.'}
          </p>
        ) : (
          visibleSpecs.map((spec, i) => (
            <SpecRow key={`${spec.attribute}-${i}`} spec={spec} resolvedSource={resolveSource(spec)} onHighlight={onHighlight} />
          ))
        )}
      </div>
    </section>
  );
}
