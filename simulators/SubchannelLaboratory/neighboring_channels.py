"""Common-plenum center-and-four-neighbor progression built on the axial solver.

The channels share geometry and inlet state. Total inlet flow is conserved and
redistributed until every parallel path has the same heated-channel pressure
drop. There is no axial crossflow or turbulent mixing between paths.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .channel_types import ChannelGeometry, ChannelInputs, ChannelResult
from .single_channel import SingleChannelModel


CHANNEL_LABELS = ("North", "East", "South", "West", "Center")


@dataclass(frozen=True)
class ParallelChannelSetting:
    label: str
    power_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if self.power_multiplier <= 0.0:
            raise ValueError("channel power multipliers must be positive")


@dataclass(frozen=True)
class NeighboringChannelResult:
    settings: tuple[ParallelChannelSetting, ...]
    channels: tuple[ChannelResult, ...]
    mass_flows_kg_s: np.ndarray
    total_mass_flow_kg_s: float
    common_pressure_drop_kpa: float
    pressure_drop_spread_kpa: float
    iteration_count: int
    converged: bool

    def __post_init__(self) -> None:
        if len(self.settings) != 5 or len(self.channels) != 5:
            raise ValueError("the NESWC common-plenum stage requires exactly five channels")

    @property
    def flow_ratios(self) -> np.ndarray:
        return self.mass_flows_kg_s / (self.total_mass_flow_kg_s / 5.0)

    @property
    def limiting_channel_index(self) -> int | None:
        values = np.asarray([channel.minimum_dnbr for channel in self.channels])
        return None if np.all(~np.isfinite(values)) else int(np.nanargmin(values))

    @property
    def limiting_node_index(self) -> int | None:
        channel_index = self.limiting_channel_index
        if channel_index is None:
            return None
        values = self.channels[channel_index].dnbr
        return None if np.all(~np.isfinite(values)) else int(np.nanargmin(values))


class CommonPlenumChannelModel:
    """Balance five parallel paths to a common pressure drop at fixed total flow."""

    def __init__(self, channel_model: SingleChannelModel | None = None) -> None:
        self.channel_model = channel_model or SingleChannelModel()

    def solve(
        self,
        geometry: ChannelGeometry,
        base_inputs: ChannelInputs,
        settings: tuple[ParallelChannelSetting, ...],
    ) -> NeighboringChannelResult:
        if len(settings) != 5:
            raise ValueError("exactly five NESWC common-plenum settings are required")
        total_flow = 5.0 * base_inputs.mass_flow_kg_s * base_inputs.flow_factor
        flows = np.full(5, total_flow / 5.0)

        def evaluate(values: np.ndarray) -> tuple[ChannelResult, ...]:
            return tuple(
                self.channel_model.solve(
                    geometry,
                    replace(
                        base_inputs,
                        mass_flow_kg_s=float(flow),
                        flow_factor=1.0,
                        power_factor=base_inputs.power_factor * setting.power_multiplier,
                    ),
                )
                for setting, flow in zip(settings, values)
            )

        tolerance = 1.0e-4
        converged = False
        channels = evaluate(flows)
        for iteration in range(1, 16):
            drops = np.asarray([channel.total_heated_pressure_drop_kpa for channel in channels])
            spread = float(np.ptp(drops))
            scale = max(float(np.mean(np.abs(drops))), 1.0)
            if spread / scale <= tolerance:
                converged = True
                break
            perturbed = flows * 1.01
            perturbed_results = evaluate(perturbed)
            perturbed_drops = np.asarray([
                channel.total_heated_pressure_drop_kpa for channel in perturbed_results
            ])
            derivatives = (perturbed_drops - drops) / (perturbed - flows)
            fallback = np.maximum(np.abs(drops) / np.maximum(flows, 1.0e-9), 1.0)
            derivatives = np.where(derivatives > 1.0e-6, derivatives, fallback)
            common_drop = float(np.sum(drops / derivatives) / np.sum(1.0 / derivatives))
            proposed = flows + (common_drop - drops) / derivatives
            minimum_flow = 0.05 * total_flow / 5.0
            proposed = np.maximum(proposed, minimum_flow)
            proposed *= total_flow / float(np.sum(proposed))
            flows = 0.45 * flows + 0.55 * proposed
            flows *= total_flow / float(np.sum(flows))
            channels = evaluate(flows)
        else:
            iteration = 15

        drops = np.asarray([channel.total_heated_pressure_drop_kpa for channel in channels])
        spread = float(np.ptp(drops))
        scale = max(float(np.mean(np.abs(drops))), 1.0)
        converged = converged or spread / scale <= tolerance
        return NeighboringChannelResult(
            settings=settings,
            channels=channels,
            mass_flows_kg_s=flows.copy(),
            total_mass_flow_kg_s=total_flow,
            common_pressure_drop_kpa=float(np.mean(drops)),
            pressure_drop_spread_kpa=spread,
            iteration_count=iteration,
            converged=converged,
        )
