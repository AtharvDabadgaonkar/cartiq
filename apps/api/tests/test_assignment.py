"""Assignment must be identical to the TypeScript implementation."""

import pytest

from cartiq_api.assignment import (
    BUCKET_COUNT,
    FNV_OFFSET_BASIS,
    InvalidSplitError,
    VariantSplit,
    assign_variant,
    bucket_of,
    fnv1a32,
)

FIFTY_FIFTY = [VariantSplit("control", 0.5), VariantSplit("treatment", 0.5)]


def test_fnv1a32_matches_shared_vectors(assignment_vectors):
    for case in assignment_vectors["hashes"]:
        assert fnv1a32(case["input"]) == case["fnv1a32"]


def test_fnv1a32_empty_string_is_offset_basis():
    assert fnv1a32("") == FNV_OFFSET_BASIS


def test_buckets_match_shared_vectors(assignment_vectors):
    salt = assignment_vectors["salt"]
    key = assignment_vectors["experiment_key"]
    for case in assignment_vectors["buckets"]:
        assert bucket_of(case["unit_id"], key, salt) == case["bucket"]


def test_assignment_is_deterministic():
    first = assign_variant("user_42", "exp", FIFTY_FIFTY, "cartiq-v1")
    assert all(
        assign_variant("user_42", "exp", FIFTY_FIFTY, "cartiq-v1") == first for _ in range(5)
    )


def test_even_split_is_balanced():
    n = 20_000
    treatment = sum(
        assign_variant(f"user_{i}", "exp", FIFTY_FIFTY, "cartiq-v1") == "treatment"
        for i in range(n)
    )
    assert abs(treatment / n - 0.5) < 0.015


def test_uneven_split_is_respected():
    variants = [VariantSplit("control", 0.9), VariantSplit("treatment", 0.1)]
    n = 20_000
    treatment = sum(
        assign_variant(f"user_{i}", "exp", variants, "cartiq-v1") == "treatment" for i in range(n)
    )
    assert abs(treatment / n - 0.1) < 0.01


def test_exposure_gates_traffic_without_reassigning():
    at_ten = {
        f"user_{i}": assign_variant(f"user_{i}", "exp", FIFTY_FIFTY, "cartiq-v1", 0.1)
        for i in range(5_000)
    }
    exposed = {k: v for k, v in at_ten.items() if v is not None}
    assert abs(len(exposed) / 5_000 - 0.1) < 0.02

    for unit, variant in exposed.items():
        assert assign_variant(unit, "exp", FIFTY_FIFTY, "cartiq-v1", 0.5) == variant


def test_buckets_stay_in_range():
    for i in range(1_000):
        assert 0 <= bucket_of(f"user_{i}", "exp", "cartiq-v1") < BUCKET_COUNT


def test_experiments_are_independent():
    identical = sum(
        bucket_of(f"u{i}", "exp_a", "cartiq-v1") == bucket_of(f"u{i}", "exp_b", "cartiq-v1")
        for i in range(500)
    )
    assert identical < 5


@pytest.mark.parametrize(
    ("variants", "exposure"),
    [
        ([], 1.0),
        ([VariantSplit("a", 0.4)], 1.0),
        (FIFTY_FIFTY, 0.0),
        (FIFTY_FIFTY, 1.5),
    ],
)
def test_invalid_splits_are_rejected(variants, exposure):
    with pytest.raises(InvalidSplitError):
        assign_variant("u", "exp", variants, "cartiq-v1", exposure)
