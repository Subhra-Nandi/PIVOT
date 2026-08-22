export function classifySpec(spec, conflicts = []) {
  if (conflicts.some((conflict) => conflict.attribute === spec.attribute)) {
    return 'conflict';
  }
  if (spec.status === 'needs_review' || spec.status === 'inferred') {
    return 'unverified';
  }
  return 'grounded';
}

export function summarizeSpecs(specifications = [], conflicts = []) {
  return specifications.reduce((counts, spec) => {
    counts[classifySpec(spec, conflicts)] += 1;
    return counts;
  }, { grounded: 0, unverified: 0, conflict: 0 });
}
