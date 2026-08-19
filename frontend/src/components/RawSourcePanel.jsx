import './Panel.css';

export default function RawSourcePanel({ label, text }) {
  return (
    <section className="panel">
      <h2 className="panel__heading">
        <span className="panel__index">01</span> Raw source
      </h2>
      <p className="panel__caption">{label}</p>
      <pre className="scan-strip">{text}</pre>
    </section>
  );
}
