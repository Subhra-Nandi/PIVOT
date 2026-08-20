// Resolving a conflict here mirrors, in JS, exactly what the Python
// pipeline's merge_records()/commerce mappers would do if you re-ran them
// after picking a source: drop the losing spec, promote the winner to
// `extracted` with a high confidence, recompute overall_confidence as the
// mean across specs, and strip the now-stale duplicate entries out of the
// two commerce docs that carry per-spec data (Schema.org's
// additionalProperty, the ETIM-style features list). Google Shopping has no
// per-spec fields, so only its confidence-derived custom_label_0 changes.
//
// This is a real, if simplified, recomputation — not a cosmetic toggle. It
// intentionally does NOT touch each document's `issues` array, since those
// check structural completeness (is there an image, a price), which a
// conflict resolution doesn't change.

const RESOLVED_CONFIDENCE = 0.97;

function confidenceBucket(score) {
  if (score >= 0.8) return 'high';
  if (score >= 0.5) return 'medium';
  return 'low';
}

export function resolveConflict(example, attribute, acceptedIndex) {
  const record = example.product_record;
  const conflict = record.validation?.conflicts?.find((c) => c.attribute === attribute);
  if (!conflict) return example;

  const acceptedValue = conflict.values[acceptedIndex];
  const acceptedSourceId = conflict.sources[acceptedIndex];

  // Specifications: drop every spec for this attribute except the one
  // matching the accepted (value, source) pair, and promote it.
  let keptSpec = null;
  const nextSpecs = [];
  for (const spec of record.specifications) {
    if (spec.attribute !== attribute) {
      nextSpecs.push(spec);
      continue;
    }
    const isAccepted = spec.value === acceptedValue && spec.source?.reference === acceptedSourceId;
    if (isAccepted && !keptSpec) {
      keptSpec = {
        ...spec,
        status: 'extracted',
        confidence: RESOLVED_CONFIDENCE,
      };
      nextSpecs.push(keptSpec);
    }
    // losing spec(s): dropped
  }

  const nextConflicts = record.validation.conflicts.filter((c) => c.attribute !== attribute);
  const overallConfidence =
    nextSpecs.reduce((sum, s) => sum + s.confidence, 0) / Math.max(nextSpecs.length, 1);

  const nextRecord = {
    ...record,
    specifications: nextSpecs,
    validation: {
      ...record.validation,
      conflicts: nextConflicts,
      overall_confidence: overallConfidence,
    },
  };

  // Commerce docs: strip the stale duplicate(s), keep one clean entry.
  const nextCommerce = { ...example.commerce };

  if (nextCommerce.schema_org) {
    const props = nextCommerce.schema_org.document.additionalProperty ?? [];
    const others = props.filter((p) => p.name !== attribute);
    const matching = props.filter((p) => p.name === attribute);
    const keptProp =
      matching.find((p) => String(parseFloat(p.value)) === String(parseFloat(acceptedValue))) ??
      matching[0];
    const resolvedProp = keptProp
      ? {
          ...keptProp,
          valueReference: { ...keptProp.valueReference, value: 'extracted' },
          description: `confidence=${RESOLVED_CONFIDENCE.toFixed(2)}, status=extracted (resolved by user)`,
        }
      : undefined;
    nextCommerce.schema_org = {
      ...nextCommerce.schema_org,
      document: {
        ...nextCommerce.schema_org.document,
        additionalProperty: resolvedProp ? [...others, resolvedProp] : others,
      },
    };
  }

  if (nextCommerce.industrial) {
    const features = nextCommerce.industrial.document.features ?? [];
    const others = features.filter((f) => f.feature_name !== attribute);
    const keptFeature = features.find((f) => f.feature_name === attribute);
    const resolvedFeature = keptFeature
      ? { ...keptFeature, status: 'extracted', confidence: RESOLVED_CONFIDENCE }
      : undefined;
    nextCommerce.industrial = {
      ...nextCommerce.industrial,
      document: {
        ...nextCommerce.industrial.document,
        features: resolvedFeature ? [...others, resolvedFeature] : others,
      },
    };
  }

  if (nextCommerce.google_shopping) {
    nextCommerce.google_shopping = {
      ...nextCommerce.google_shopping,
      document: {
        ...nextCommerce.google_shopping.document,
        custom_label_0: confidenceBucket(overallConfidence),
      },
    };
  }

  return { ...example, product_record: nextRecord, commerce: nextCommerce };
}
