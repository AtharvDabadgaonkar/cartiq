import { describe, expect, it } from 'vitest';
import vectors from '../__fixtures__/assignment-vectors.json';
import { assignVariant, bucketOf, BUCKET_COUNT, fnv1a32, InvalidSplitError } from '../assignment';

const SALT = vectors.salt;
const EXP = vectors.experiment_key;
const FIFTY_FIFTY = [
  { key: 'control', weight: 0.5 },
  { key: 'treatment', weight: 0.5 },
] as const;

describe('fnv1a32', () => {
  it('matches the cross-language reference vectors', () => {
    for (const { input, fnv1a32: expected } of vectors.hashes) {
      expect(fnv1a32(input)).toBe(expected);
    }
  });

  it('is stable for the empty string (FNV offset basis)', () => {
    expect(fnv1a32('')).toBe(0x811c9dc5);
  });
});

describe('bucketOf', () => {
  it('matches the cross-language reference buckets', () => {
    for (const { unit_id, bucket } of vectors.buckets) {
      expect(bucketOf(unit_id, EXP, SALT)).toBe(bucket);
    }
  });

  it('stays inside the bucket space', () => {
    for (let i = 0; i < 1000; i++) {
      const b = bucketOf(`user_${i}`, EXP, SALT);
      expect(b).toBeGreaterThanOrEqual(0);
      expect(b).toBeLessThan(BUCKET_COUNT);
    }
  });

  it('separates experiments: the same user is not correlated across keys', () => {
    const a = Array.from({ length: 500 }, (_, i) => bucketOf(`u${i}`, 'exp_a', SALT));
    const b = Array.from({ length: 500 }, (_, i) => bucketOf(`u${i}`, 'exp_b', SALT));
    const identical = a.filter((v, i) => v === b[i]).length;
    expect(identical).toBeLessThan(5);
  });
});

describe('assignVariant', () => {
  it('is deterministic', () => {
    const first = assignVariant('user_42', EXP, FIFTY_FIFTY, SALT);
    for (let i = 0; i < 10; i++) {
      expect(assignVariant('user_42', EXP, FIFTY_FIFTY, SALT)).toBe(first);
    }
  });

  it('splits 50/50 within 1.5pp over 20k units', () => {
    let treatment = 0;
    const n = 20_000;
    for (let i = 0; i < n; i++) {
      if (assignVariant(`user_${i}`, EXP, FIFTY_FIFTY, SALT) === 'treatment') treatment++;
    }
    expect(Math.abs(treatment / n - 0.5)).toBeLessThan(0.015);
  });

  it('honours uneven splits', () => {
    const variants = [
      { key: 'control', weight: 0.9 },
      { key: 'treatment', weight: 0.1 },
    ];
    let treatment = 0;
    const n = 20_000;
    for (let i = 0; i < n; i++) {
      if (assignVariant(`user_${i}`, EXP, variants, SALT) === 'treatment') treatment++;
    }
    expect(Math.abs(treatment / n - 0.1)).toBeLessThan(0.01);
  });

  it('gates traffic by exposure without reassigning exposed units', () => {
    const atTen = new Map<string, string | null>();
    for (let i = 0; i < 5000; i++) {
      const id = `user_${i}`;
      atTen.set(id, assignVariant(id, EXP, FIFTY_FIFTY, SALT, 0.1));
    }
    const exposed = [...atTen.values()].filter((v) => v !== null).length;
    expect(Math.abs(exposed / 5000 - 0.1)).toBeLessThan(0.02);

    // Ramping to 50% must keep every already-exposed unit on its variant.
    for (const [id, variant] of atTen) {
      if (variant === null) continue;
      expect(assignVariant(id, EXP, FIFTY_FIFTY, SALT, 0.5)).toBe(variant);
    }
  });

  it('rejects malformed splits', () => {
    expect(() => assignVariant('u', EXP, [], SALT)).toThrow(InvalidSplitError);
    expect(() => assignVariant('u', EXP, [{ key: 'a', weight: 0.4 }], SALT)).toThrow(
      InvalidSplitError,
    );
    expect(() => assignVariant('u', EXP, FIFTY_FIFTY, SALT, 1.5)).toThrow(InvalidSplitError);
  });
});
