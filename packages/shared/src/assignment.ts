/**
 * Deterministic experiment assignment.
 *
 * Requirements that drive the design:
 *  - Same user + same experiment => same variant, forever, with no storage.
 *  - Identical results in TypeScript (storefront) and Python (simulator, stats
 *    engine), otherwise a simulated experiment cannot be trusted. Both sides
 *    implement FNV-1a 32-bit and are pinned to the shared vectors in
 *    `src/__fixtures__/assignment-vectors.json`.
 *  - Changing the salt reshuffles everyone, so the salt is fixed per experiment
 *    generation, never per request.
 */

/** FNV-1a, 32-bit, over UTF-8 bytes. Chosen for being trivial to reimplement exactly. */
export function fnv1a32(input: string): number {
  let hash = 0x811c9dc5;
  const bytes = new TextEncoder().encode(input);
  for (const byte of bytes) {
    hash ^= byte;
    // 16777619, via shifts, to stay inside 32-bit integer math.
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash >>> 0;
}

export const BUCKET_COUNT = 10_000;

/** Stable bucket in [0, 10000) for a unit inside one experiment. */
export function bucketOf(unitId: string, experimentKey: string, salt: string): number {
  return fnv1a32(`${salt}:${experimentKey}:${unitId}`) % BUCKET_COUNT;
}

export interface VariantSplit {
  /** Variant key, e.g. "control" | "treatment". */
  key: string;
  /** Share of traffic in [0, 1]. Weights across an experiment must sum to 1. */
  weight: number;
}

export class InvalidSplitError extends Error {}

/**
 * Assigns a unit to a variant by walking the cumulative weights in declared
 * order, so adding a variant at the end does not move existing units.
 * Returns null when the unit falls outside the experiment's exposure.
 */
export function assignVariant(
  unitId: string,
  experimentKey: string,
  variants: readonly VariantSplit[],
  salt: string,
  /** Share of all traffic eligible for the experiment, for staged rollout. */
  exposure = 1,
): string | null {
  if (variants.length === 0) throw new InvalidSplitError('experiment has no variants');
  const total = variants.reduce((sum, v) => sum + v.weight, 0);
  if (Math.abs(total - 1) > 1e-6) {
    throw new InvalidSplitError(`variant weights must sum to 1, got ${total}`);
  }
  if (exposure <= 0 || exposure > 1) {
    throw new InvalidSplitError(`exposure must be in (0, 1], got ${exposure}`);
  }

  const bucket = bucketOf(unitId, experimentKey, salt);

  // Exposure gate uses a separate hash namespace so ramping exposure up does
  // not reassign anyone already inside the experiment.
  if (exposure < 1) {
    const gate = fnv1a32(`${salt}:${experimentKey}:exposure:${unitId}`) % BUCKET_COUNT;
    if (gate >= Math.round(exposure * BUCKET_COUNT)) return null;
  }

  let cumulative = 0;
  for (const variant of variants) {
    cumulative += variant.weight * BUCKET_COUNT;
    if (bucket < cumulative) return variant.key;
  }
  // Only reachable through floating-point slack on the final boundary.
  return variants[variants.length - 1]!.key;
}
