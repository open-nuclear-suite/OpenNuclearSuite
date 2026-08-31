"""Plant-model boundary for the thermal-hydraulics teaching simulator.

Dedicated PWR and BWR engines implement the same small integration contract
without sharing plant-specific equations or public state/control contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

import numpy as np

from steam_properties import SteamTables
from pwr_plant_model import PWRPlantModel as IndependentPWRPlantModel
from bwr_plant_model import BWRPlantModel as IndependentBWRPlantModel


class CapabilityStatus(str, Enum):
    IMPLEMENTED = "implemented"
    TEACHING_SURROGATE = "teaching surrogate"
    DIAGNOSTIC_ONLY = "diagnostic only"
    NOT_IMPLEMENTED = "not implemented"


@dataclass(frozen=True)
class PlantModelMetadata:
    key: str
    label: str
    development_status: str
    scenario_capable: bool
    hot_channel_capable: bool
    capabilities: Mapping[str, CapabilityStatus] = field(default_factory=dict)


class PlantModel(ABC):
    """Stable interface consumed by state integration and front ends."""

    metadata: PlantModelMetadata

    def initialize_state(self, state: Any) -> None:
        """Populate plant-specific state fields after generic state creation."""

    @abstractmethod
    def pack(self, state: Any) -> np.ndarray:
        """Pack a public simulator state into the model's integration vector."""

    @abstractmethod
    def step(self, state: Any, controls: Any, dt: float) -> Any:
        """Advance a public simulator state and return step diagnostics."""

    @abstractmethod
    def pressure_eccs_factor(self, pressure: float) -> float:
        """Return the model-specific pressure-dependent injection fraction."""


class PWRPlantModel(IndependentPWRPlantModel, PlantModel):
    """Dedicated reduced-order PWR plant model."""

    metadata = PlantModelMetadata(
        key="PWR", label="Representative PWR", development_status="implemented",
        scenario_capable=True, hot_channel_capable=True,
        capabilities={
            "lumped_transient": CapabilityStatus.IMPLEMENTED,
            "hot_channel": CapabilityStatus.IMPLEMENTED,
            "accident_scenarios": CapabilityStatus.IMPLEMENTED,
            "safety_logic": CapabilityStatus.IMPLEMENTED,
            "safety_system_hydraulics": CapabilityStatus.TEACHING_SURROGATE,
            "reduced_axial_dynamics": CapabilityStatus.TEACHING_SURROGATE,
            "scenario_envelopes": CapabilityStatus.TEACHING_SURROGATE,
            "uncertainty_sensitivity_screening": CapabilityStatus.TEACHING_SURROGATE,
            "public_parameter_provenance": CapabilityStatus.IMPLEMENTED,
        },
    )


class BWRPlantModel(IndependentBWRPlantModel, PlantModel):
    """Independent core/downcomer/steam-dome BWR vessel model."""

    metadata = PlantModelMetadata(
        key="BWR", label="Representative BWR",
        development_status="R9 source-parameterized feature prototype",
        scenario_capable=True, hot_channel_capable=True,
        capabilities={
            "vessel_balances": CapabilityStatus.IMPLEMENTED,
            "direct_cycle": CapabilityStatus.IMPLEMENTED,
            "void_feedback": CapabilityStatus.TEACHING_SURROGATE,
            "recirculation_head_balance": CapabilityStatus.IMPLEMENTED,
            "recirculation_hydraulics": CapabilityStatus.TEACHING_SURROGATE,
            "safety_logic": CapabilityStatus.IMPLEMENTED,
            "safety_system_hydraulics": CapabilityStatus.TEACHING_SURROGATE,
            "suppression_pool_balance": CapabilityStatus.IMPLEMENTED,
            "level_instrumentation": CapabilityStatus.TEACHING_SURROGATE,
            "reference_leg_dynamics": CapabilityStatus.IMPLEMENTED,
            "suppression_pool": CapabilityStatus.TEACHING_SURROGATE,
            "axial_channel": CapabilityStatus.DIAGNOSTIC_ONLY,
            "open_xl_critical_power": CapabilityStatus.DIAGNOSTIC_ONLY,
            "boiling_crisis_heat_transfer": CapabilityStatus.TEACHING_SURROGATE,
            "channel_pressure_loss": CapabilityStatus.IMPLEMENTED,
            "reduced_axial_dynamics": CapabilityStatus.TEACHING_SURROGATE,
            "scenario_envelopes": CapabilityStatus.TEACHING_SURROGATE,
            "uncertainty_sensitivity_screening": CapabilityStatus.TEACHING_SURROGATE,
            "public_parameter_provenance": CapabilityStatus.IMPLEMENTED,
            "equilibrium_vessel_flash": CapabilityStatus.IMPLEMENTED,
            "core_vapor_inventory": CapabilityStatus.IMPLEMENTED,
            "validated_mcpr": CapabilityStatus.NOT_IMPLEMENTED,
            "upper_plenum_separator_storage": CapabilityStatus.IMPLEMENTED,
            "dynamic_separator": CapabilityStatus.TEACHING_SURROGATE,
        },
    )


PLANT_MODEL_TYPES = {
    "PWR": PWRPlantModel,
    "BWR": BWRPlantModel,
}


def create_plant_model(
    plant_type: str, constants: Any, properties: SteamTables | None = None,
) -> PlantModel:
    key = str(plant_type).upper()
    try:
        model_type = PLANT_MODEL_TYPES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown plant type: {plant_type}") from exc
    return model_type(constants, properties)
