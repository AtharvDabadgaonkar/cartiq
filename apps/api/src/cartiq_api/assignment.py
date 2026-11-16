"""Deterministic experiment assignment — the Python twin of the TypeScript one.

The simulator and the stats engine must bucket units exactly as the storefront
does, otherwise a "recovered" treatment effect would be an artefact of two
different hash functions. Both implementations are pinned to the shared vectors
in packages/shared/src/__fixtures__/assignment-vectors.json.
"""

from dataclasses import dataclass

FNV_OFFSET_BASIS = 0x811C9DC5
FNV_PRIME = 0x01000193
UINT32_MASK = 0xFFFFFFFF
BUCKET_COUNT = 10_000


class InvalidSplitError(ValueError):
    """Raised when variant weights or exposure are not a valid split."""


def fnv1a32(value: str) -> int:
    """Return the 32-bit FNV-1a hash of `value`'s UTF-8 bytes."""
    hashed = FNV_OFFSET_BASIS
    for byte in value.encode("utf-8"):
        hashed ^= byte
        hashed = (hashed * FNV_PRIME) & UINT32_MASK
    return hashed


def bucket_of(unit_id: str, experiment_key: str, salt: str) -> int:
    """Return the stable bucket in [0, BUCKET_COUNT) for a unit in an experiment."""
    return fnv1a32(f"{salt}:{experiment_key}:{unit_id}") % BUCKET_COUNT


@dataclass(frozen=True)
class VariantSplit:
    """One variant and its share of traffic."""

    key: str
    weight: float


def assign_variant(
    unit_id: str,
    experiment_key: str,
    variants: list[VariantSplit],
    salt: str,
    exposure: float = 1.0,
) -> str | None:
    """Assign a unit to a variant, or None when it falls outside the exposure.

    Args:
        unit_id: Stable unit of randomisation (a user id).
        experiment_key: Stable experiment key; never change it on a live test.
        variants: Variants in declared order; weights must sum to 1.
        salt: Generation salt. Changing it reshuffles every assignment.
        exposure: Share of eligible traffic in the experiment, for staged rollout.

    Raises:
        InvalidSplitError: If the split or exposure is malformed.
    """
    if not variants:
        raise InvalidSplitError("experiment has no variants")
    total = sum(v.weight for v in variants)
    if abs(total - 1.0) > 1e-6:
        raise InvalidSplitError(f"variant weights must sum to 1, got {total}")
    if not 0.0 < exposure <= 1.0:
        raise InvalidSplitError(f"exposure must be in (0, 1], got {exposure}")

    bucket = bucket_of(unit_id, experiment_key, salt)

    # Separate hash namespace, so ramping exposure never reassigns an exposed unit.
    if exposure < 1.0:
        gate = fnv1a32(f"{salt}:{experiment_key}:exposure:{unit_id}") % BUCKET_COUNT
        if gate >= round(exposure * BUCKET_COUNT):
            return None

    cumulative = 0.0
    for variant in variants:
        cumulative += variant.weight * BUCKET_COUNT
        if bucket < cumulative:
            return variant.key
    return variants[-1].key
