import ConflictBanner from './ConflictBanner';
import SpecRow from './SpecRow';
import './Panel.css';
import './VerifiedRecord.css';

export default function VerifiedRecord({ record }) {
  const sourcesUsed = record.provenance?.sources_used ?? [];
  const resolveSource = (spec) =>
    spec.source ? sourcesUsed.find((s) => s.id === spec.source.reference) : undefined;

  return (
    <section className="panel">
      <h2 className="panel__heading">
        <span className="panel__index">02</span> Verified record
      </h2>
      <p className="panel__caption">
        {record.product_name}
        {record.brand ? ` \u00b7 ${record.brand}` : ''}
      </p>

      <ConflictBanner conflicts={record.validation?.conflicts} sourcesUsed={sourcesUsed} />

      <div className="spec-table">
        {record.specifications.length === 0 ? (
          <p className="spec-table__empty">No specifications extracted.</p>
        ) : (
          record.specifications.map((spec, i) => (
            <SpecRow key={`${spec.attribute}-${i}`} spec={spec} resolvedSource={resolveSource(spec)} />
          ))
        )}
      </div>
    </section>
  );
}
