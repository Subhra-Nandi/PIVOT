// Citation sync matches on "<value> <unit>" rather than the stored
// citation snippet verbatim: the demo fixtures' snippets carry extra
// section-context text (e.g. "[Mechanical] Tensile strength: 400 MPa...")
// that the raw source text itself doesn't contain, so a literal substring
// match would silently miss. Matching the number+unit is what's actually
// stable across both.
function splitOnMatch(text, searchText) {
  if (!searchText) return [{ text, match: false }];
  const idx = text.toLowerCase().indexOf(searchText.toLowerCase());
  if (idx === -1) return [{ text, match: false }];
  return [
    { text: text.slice(0, idx), match: false },
    { text: text.slice(idx, idx + searchText.length), match: true },
    { text: text.slice(idx + searchText.length), match: false },
  ];
}

export default function SourceInspector({ label, text, activeSnippet }) {
  const segments = splitOnMatch(text, activeSnippet);

  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 backdrop-blur-md">
      <div className="mb-3 flex items-baseline gap-2">
        <span className="font-mono text-xs text-zinc-600">01</span>
        <h2 className="font-display text-sm font-semibold text-zinc-100">Raw source</h2>
      </div>
      <p className="mb-3 font-mono text-[11px] text-zinc-500">{label}</p>

      <pre className="thin-scroll max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-zinc-800/80 bg-zinc-950 p-4 font-mono text-xs leading-relaxed text-zinc-300">
        {segments.map((seg, i) =>
          seg.match ? (
            <mark
              key={i}
              className="rounded bg-lime-400/10 px-0.5 text-lime-300 ring-2 ring-lime-400/80 transition-all duration-200"
            >
              {seg.text}
            </mark>
          ) : (
            <span key={i}>{seg.text}</span>
          )
        )}
      </pre>
    </section>
  );
}
