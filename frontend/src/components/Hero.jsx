import StampBadge from './StampBadge';
import './Hero.css';

function overallVariant(confidence) {
  if (confidence >= 0.8) return 'pass';
  if (confidence >= 0.5) return 'note';
  return 'hold';
}

export default function Hero({ overallConfidence }) {
  const hasConfidence = typeof overallConfidence === 'number';
  return (
    <header className="hero">
      <div className="hero__title-block">
        <p className="hero__eyebrow">Product Intelligence — Inspection Report</p>
        <h1 className="hero__title">PIVOT</h1>
        <p className="hero__subtitle">
          Every field on this record traces back to a source, a page, and a
          confidence score. Nothing here was taken on faith.
        </p>
      </div>
      {hasConfidence && (
        <div className="hero__stamp-block">
          <StampBadge variant={overallVariant(overallConfidence)} size="lg" />
          <span className="hero__confidence">
            {(overallConfidence * 100).toFixed(0)}% overall confidence
          </span>
        </div>
      )}
    </header>
  );
}
