/**
 * Regenerates packages/shared/src/__fixtures__/assignment-vectors.json.
 * Run only when the hash function intentionally changes (which reshuffles every
 * historical assignment, so expect to rename experiments too).
 *   node scripts/gen_assignment_vectors.mjs
 */
import { writeFileSync } from 'node:fs';

function fnv1a32(s) {
  let h = 0x811c9dc5;
  for (const b of new TextEncoder().encode(s)) {
    h ^= b;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

const salt = 'cartiq-v1';
const experimentKey = 'flagship_assistant_nudges';
const units = ['user_0', 'user_1', 'user_42', 'user_999', 'a', 'Ωmega-user', '1234567890abcdef'];

const vectors = {
  _comment:
    'Shared FNV-1a/bucketing test vectors. TS and Python assignment implementations must both reproduce these exactly. Regenerate with scripts/gen_assignment_vectors.mjs',
  salt,
  experiment_key: experimentKey,
  bucket_count: 10000,
  hashes: units.map((u) => ({
    input: `${salt}:${experimentKey}:${u}`,
    fnv1a32: fnv1a32(`${salt}:${experimentKey}:${u}`),
  })),
  buckets: units.map((u) => ({
    unit_id: u,
    bucket: fnv1a32(`${salt}:${experimentKey}:${u}`) % 10000,
  })),
};

writeFileSync(
  new URL('../packages/shared/src/__fixtures__/assignment-vectors.json', import.meta.url),
  JSON.stringify(vectors, null, 2) + '\n',
);
console.log(`wrote ${vectors.buckets.length} vectors`);
