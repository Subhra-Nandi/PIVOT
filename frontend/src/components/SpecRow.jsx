import { useState } from 'react';
import StatusBadge from './StatusBadge';

const BAR_COLOR = {
  extracted: 'bg-emerald-400',
  inferred: 'bg-amber-400',
  needs_review: 'bg-rose-400',
};

export default function SpecRow({ spec, resolvedSource, onSnippetHover }) {
  const [open, setOpen] = useState(false);
  const hasCitation = Boolean(spec.source);
  const searchText = `${spec.value}${spec.unit ? ` ${spec.unit}` : ''}`;

  return (
    <div
      className="rounded-xl border border-zinc-800/80 bg-zinc-950/60 transition-colors duration-150 hover:border-zinc-700"
      onMouseEnter={() => hasCitation && onSnippetHover(searchText)}
      onMouseLeave={() => onSnippetHover(null)}
    >
      <button
        type="button"
        onClick={() => {
          if (!hasCitation) return;
          setOpen((v) => !v);
          onSnippetHover(searchText);
        }}
        aria-expanded={open}
        disabled={!hasCitation}
        className="grid w-full grid-cols-[1fr_auto_auto_auto] items-center gap-3 px-4 py-3 text-left disabled:cursor-default"
      >
        <span className="truncate font-mono text-xs text-zinc-400">
          {spec.attribute.replaceAll('_', ' ')}
        </span>
        <span className="font-mono text-sm font-medium text-zinc-100">
          {spec.value}
          {spec.unit ? ` ${spec.unit}` : ''}
        </span>
        <span className="hidden items-center gap-1.5 sm:flex">
          <span className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-800">
            <span
              className={`block h-full rounded-full ${BAR_COLOR[spec.status] ?? 'bg-zinc-500'}`}
              style={{ width: `${Math.round(spec.confidence * 100)}%` }}
            />
          </span>
          <span className="font-mono text-[10px] text-zinc-500">
            {(spec.confidence * 100).toFixed(0)}%
          </span>
        </span>
        <StatusBadge status={spec.status} />
      </button>

      {open && hasCitation && (
        <div className="border-t border-zinc-800/80 px-4 py-3">
          <p className="font-mono text-[11px] text-zinc-500">
            {resolvedSource ? (
              <>
                Source: {resolvedSource.type} &middot; {resolvedSource.reference}
                {typeof resolvedSource.page === 'number' ? ` \u00b7 p.${resolvedSource.page}` : ''}
              </>
            ) : (
              <>Source reference: {spec.source.reference} (unresolved)</>
            )}
          </p>
          {spec.source.snippet && (
            <p className="mt-1.5 rounded-lg bg-zinc-900 px-3 py-2 font-mono text-[11px] italic text-zinc-400">
              &ldquo;{spec.source.snippet}&rdquo;
            </p>
          )}
        </div>
      )}
    </div>
  );
}
