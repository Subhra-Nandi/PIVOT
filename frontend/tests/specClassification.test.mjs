import assert from 'node:assert/strict';
import { classifySpec, summarizeSpecs } from '../src/lib/specClassification.js';

const customSpecs = [
  { attribute: 'voltage_rating', status: 'extracted' },
  { attribute: 'horsepower', status: 'needs_review' },
  { attribute: 'shaft_diameter', status: 'needs_review' },
  { attribute: 'insulation_class', status: 'needs_review' },
  { attribute: 'mounting_style', status: 'needs_review' },
  { attribute: 'color_code', status: 'needs_review' },
];

assert.deepEqual(summarizeSpecs(customSpecs, []), {
  grounded: 1,
  unverified: 5,
  conflict: 0,
});
assert.equal(classifySpec(customSpecs[1], []), 'unverified');
assert.equal(classifySpec(customSpecs[0], [{ attribute: 'voltage_rating' }]), 'conflict');
