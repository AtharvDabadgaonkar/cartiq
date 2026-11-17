import 'server-only';
import { assignVariant } from '@cartiq/shared';
import { prisma } from '@/lib/db';
import { serverEnv } from '@/lib/env';

/**
 * Feature flag evaluation.
 *
 * A flag is on for a visitor when it is enabled AND either their deterministic
 * bucket falls inside the rollout, or they are on the flag's "on" variant of a
 * linked experiment. Assignment uses the same FNV-1a function as the simulator
 * and the stats engine, so a flag decision in the browser and in an analysis
 * agree by construction rather than by luck.
 */
export async function enabledFlagsFor(unitId: string): Promise<Set<string>> {
  const salt = serverEnv().FLAG_HASH_SALT;
  const flags = await prisma.featureFlag.findMany({
    include: { experiment: { include: { variants: { orderBy: { position: 'asc' } } } } },
  });

  const enabled = new Set<string>();
  for (const flag of flags) {
    if (!flag.enabled) continue;

    if (flag.experiment && flag.onVariant) {
      const variants = flag.experiment.variants.map((variant) => ({
        key: variant.key,
        weight: Number(variant.weight),
      }));
      if (variants.length === 0) continue;
      const assigned = assignVariant(
        unitId,
        flag.experiment.key,
        variants,
        salt,
        Number(flag.experiment.exposure),
      );
      if (assigned === flag.onVariant) enabled.add(flag.key);
      continue;
    }

    const rollout = Number(flag.rollout);
    if (rollout >= 1) {
      enabled.add(flag.key);
    } else if (rollout > 0) {
      // A percentage rollout is an experiment with one variant: same hash, so
      // ramping it never reshuffles who already has the flag.
      const assigned = assignVariant(
        unitId,
        `flag:${flag.key}`,
        [
          { key: 'on', weight: rollout },
          { key: 'off', weight: 1 - rollout },
        ],
        salt,
      );
      if (assigned === 'on') enabled.add(flag.key);
    }
  }
  return enabled;
}
