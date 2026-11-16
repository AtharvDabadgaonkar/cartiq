"""docs/SIMULATION.md must document every simulator parameter.

The honesty rule says the simulator's assumptions are explicit and documented.
That is only true if the documentation cannot silently fall behind the code,
so this test fails the build when a parameter is added without a mention.
"""

import dataclasses
from pathlib import Path

import pytest

from cartiq_api.simulation import DEFAULT_PARAMS
from cartiq_api.simulation.params import TRANSITION_KEYS

REPO_ROOT = Path(__file__).resolve().parents[3]
SIMULATION_MD = REPO_ROOT / "docs" / "SIMULATION.md"


@pytest.fixture(scope="module")
def doc() -> str:
    return SIMULATION_MD.read_text()


def test_every_parameter_is_documented(doc):
    undocumented = [
        field.name for field in dataclasses.fields(DEFAULT_PARAMS) if field.name not in doc
    ]
    assert not undocumented, f"undocumented simulator parameters: {undocumented}"


def test_every_intervention_and_its_effects_are_documented(doc):
    for key, intervention in DEFAULT_PARAMS.interventions.items():
        assert key in doc, f"intervention {key} is not documented"
        for multiplier in intervention.effects.values():
            if multiplier == 1.0:
                continue
            assert f"{multiplier}" in doc, f"{key} effect {multiplier} is not documented"


def test_every_funnel_transition_is_documented(doc):
    # Written with arrows in prose, so compare on the step names.
    for transition in TRANSITION_KEYS:
        origin, destination = transition.split("->")
        assert origin.replace("_", " ") in doc.lower()
        assert destination.replace("_", " ") in doc.lower()


def test_the_doc_states_the_two_honesty_rules(doc):
    lowered = doc.lower()
    assert "simulated" in lowered
    assert "not a real-world result" in lowered or "never presented as a real-world" in lowered
    # The effect must be described as an input the estimator cannot read.
    assert "input" in lowered and "a/a" in lowered


def test_the_doc_lists_what_is_not_modelled(doc):
    # Silence about a limitation reads as a claim; the doc must state them.
    assert "does *not* model" in doc or "does not model" in doc


def test_the_seed_is_documented_as_fixed(doc):
    assert str(DEFAULT_PARAMS.seed) in doc
    assert "reproducib" in doc.lower()
