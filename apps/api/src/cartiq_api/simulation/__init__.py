"""Reproducible shopper-session simulator.

Exists because the real dataset contains no experiment: nobody ever shipped an
AI assistant or a recovery nudge to those shoppers, so there is no treatment
group to measure. Rather than claim a lift that was never observed, CartIQ
generates sessions from explicit behavioural parameters and then has to recover
the configured effect through ordinary statistics.

Every parameter, including each intervention's treatment effect, is documented
in docs/SIMULATION.md. The Experiment Studio is never told what the effect is.
"""

from cartiq_api.simulation.engine import SimulationOutput, simulate
from cartiq_api.simulation.params import (
    DEFAULT_PARAMS,
    ExperimentSpec,
    InterventionParams,
    SimulationParams,
)

__all__ = [
    "DEFAULT_PARAMS",
    "ExperimentSpec",
    "InterventionParams",
    "SimulationOutput",
    "SimulationParams",
    "simulate",
]
