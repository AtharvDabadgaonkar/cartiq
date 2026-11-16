"""The committed seed sample must stay internally consistent and attributed."""

import json
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_DIR = REPO_ROOT / "data" / "seed"

pytestmark = pytest.mark.skipif(
    not (SEED_DIR / "manifest.json").exists(),
    reason="seed sample not built (python scripts/build_seed.py)",
)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads((SEED_DIR / "manifest.json").read_text())


def test_manifest_attributes_the_real_half(manifest):
    real = manifest["real"]
    assert real["licence"] == "CC BY 4.0"
    assert "doi.org" in real["attribution"]
    assert real["url"].startswith("https://archive.ics.uci.edu")


def test_manifest_labels_the_simulated_half(manifest):
    simulated = manifest["simulated"]
    assert "SIMULATED" in simulated["warning"]
    assert simulated["documented_in"] == "docs/SIMULATION.md"
    assert isinstance(simulated["seed"], int)


def test_real_events_never_claim_unobservable_fields():
    events = pd.read_csv(SEED_DIR / "events_real.csv.gz")
    assert set(events["device"]) == {"unknown"}
    assert set(events["traffic_source"]) == {"unknown"}
    assert events["page"].isna().all()


def test_simulated_events_do_carry_device_and_attribution():
    events = pd.read_csv(SEED_DIR / "events_simulated.csv.gz")
    assert "unknown" not in set(events["device"])
    assert events["page"].notna().all()


def test_counts_match_the_manifest(manifest):
    real = pd.read_csv(SEED_DIR / "events_real.csv.gz")
    simulated = pd.read_csv(SEED_DIR / "events_simulated.csv.gz")
    products = pd.read_csv(SEED_DIR / "products.csv.gz")
    assert len(real) == manifest["real"]["events"]
    assert len(simulated) == manifest["simulated"]["events"]
    assert len(products) == manifest["real"]["products"]


def test_every_referenced_product_is_in_the_seed_catalog():
    events = pd.read_csv(SEED_DIR / "events_real.csv.gz")
    products = pd.read_csv(SEED_DIR / "products.csv.gz")
    referenced = set(events["product_id"].dropna().astype(str))
    assert referenced <= set(products["product_id"].astype(str))


def test_seed_stays_small_enough_to_commit():
    total = sum(f.stat().st_size for f in SEED_DIR.glob("*.gz"))
    assert total < 5_000_000, f"seed is {total / 1e6:.1f} MB; keep it committable"
