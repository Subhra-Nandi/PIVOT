export default function ConflictDiffCard({ conflicts, sourcesUsed, onResolve }) {
  if (!conflicts || conflicts.length === 0) return null;

  const referenceLabel = (sourceId) => {
    const source = sourcesUsed.find((s) => s.id === sourceId);
    return source ? source.reference : sourceId;
  };

  return (
    <div className="mb-4 space-y-3">
      {conflicts.map((conflict) => (
        <div
          key={conflict.attribute}
          className="rounded-xl border border-rose-500/30 bg-rose-500/[0.04] p-4"
        >
          <div className="mb-3 flex items-center gap-2">
            <span className="inline-flex items-center rounded-md border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide text-rose-400">
              Conflict
            </span>
            <span className="font-mono text-xs text-zinc-300">
              {conflict.attribute.replaceAll('_', ' ')} &mdash; sources disagree
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {conflict.values.map((value, i) => (
              <div
                key={i}
                className="flex flex-col justify-between rounded-lg border border-zinc-800 bg-zinc-950 p-3"
              >
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-wide text-zinc-500">
                    Source {String.fromCharCode(65 + i)}
                  </p>
                  <p className="mt-1 font-mono text-sm font-semibold text-zinc-100">{value}</p>
                  <p className="mt-0.5 font-mono text-[11px] text-zinc-500">
                    {referenceLabel(conflict.sources[i])}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onResolve(conflict.attribute, i)}
                  className="mt-3 w-full rounded-lg bg-lime-400 px-3 py-1.5 font-mono text-[11px] font-semibold text-zinc-950 transition-colors duration-150 hover:bg-lime-300"
                >
                  Resolve &amp; Override
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
