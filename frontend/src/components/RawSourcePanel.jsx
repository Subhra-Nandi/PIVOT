import { useEffect, useRef } from 'react';
import './Panel.css';

/** Strips make_snippet()'s presentation additions (a "[Section] " prefix,
 * a trailing ellipsis on truncation) so the remaining text has a chance of
 * matching verbatim inside the raw source — those additions exist for
 * readability in the citation popover, not for search. */
function cleanSnippetForMatch(snippet) {
  return snippet
    .replace(/^\[[^\]]*\]\s*/, '')
    .replace(/\u2026$/, '')
    .trim();
}

function renderWithHighlight(text, snippet) {
  if (!snippet) return { node: text, matched: false };
  const needle = cleanSnippetForMatch(snippet);
  if (!needle) return { node: text, matched: false };
  const idx = text.indexOf(needle);
  if (idx === -1) return { node: text, matched: false }; // snippet doesn't literally appear (e.g. a catalog cell reference)
  return {
    node: (
      <>
        {text.slice(0, idx)}
        <mark>{text.slice(idx, idx + needle.length)}</mark>
        {text.slice(idx + needle.length)}
      </>
    ),
    matched: true,
  };
}

export default function RawSourcePanel({ label, text, highlightSnippet }) {
  const preRef = useRef(null);
  const { node, matched } = renderWithHighlight(text, highlightSnippet);

  useEffect(() => {
    if (!matched || !preRef.current) return;
    const mark = preRef.current.querySelector('mark');
    mark?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [highlightSnippet, matched]);

  return (
    <section className="panel">
      <h2 className="panel__heading">
        <span className="panel__index">01</span> Raw source
      </h2>
      <p className="panel__caption">
        {label}
        {matched && <span className="panel__hint"> — highlighted field jumped to below</span>}
      </p>
      <pre className="scan-strip" ref={preRef}>
        {node}
      </pre>
    </section>
  );
}
