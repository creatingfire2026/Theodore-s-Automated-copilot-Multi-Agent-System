"""Real-time Agent Swarm Router — sector routing, safety gates, and threat levels.

High-impact tasks (lockdown / barrier / elite) stay in `pending_authorization`
and are not bound for execution until `authorize(task_id)` is called.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Set


class Sector(Enum):
    NORTH = "North"
    SOUTH = "South"
    EAST = "East"
    WEST = "West"
    CORE = "Core"


class ThreatLevel(IntEnum):
    L0_STABLE = 0
    L1_NOMINAL = 1
    L2_ELEVATED = 2
    L3_HIGH = 3
    L4_CRITICAL = 4
    L5_GLOBAL_EMERGENCY = 5


@dataclass
class SectorMetrics:
    jitter: float = 0.0
    drift: float = 0.0
    stagnation: float = 0.0
    emotional_noise: float = 0.0
    ghost_echoes: bool = False
    inward_vector_to_core: bool = False
    active_tasks: List[str] = field(default_factory=list)


@dataclass
class RoutingWeights:
    sector_weights: Dict[Sector, float] = field(default_factory=lambda: {s: 1.0 for s in Sector})


HIGH_IMPACT_MARKERS = ("lockdown", "barrier", "elite")

ADJACENCY_MAP = {
    Sector.NORTH: [Sector.EAST, Sector.WEST],
    Sector.SOUTH: [Sector.EAST, Sector.WEST],
    Sector.EAST: [Sector.NORTH, Sector.SOUTH, Sector.CORE],
    Sector.WEST: [Sector.NORTH, Sector.SOUTH, Sector.CORE],
    Sector.CORE: [Sector.NORTH, Sector.SOUTH, Sector.EAST, Sector.WEST],
}


def is_high_impact(task_id: str) -> bool:
    lowered = str(task_id).lower()
    return any(marker in lowered for marker in HIGH_IMPACT_MARKERS)


class AgentSwarmRouter:
    def __init__(self, hysteresis_cycles: int = 2):
        if hysteresis_cycles < 1:
            raise ValueError("hysteresis_cycles must be >= 1")
        self.hysteresis_cycles = hysteresis_cycles
        self.threat_level = ThreatLevel.L0_STABLE
        self.global_battlefield_mode = False
        self.sector_state: Dict[Sector, SectorMetrics] = {s: SectorMetrics() for s in Sector}
        self.routing_weights = RoutingWeights()

        self.diagnostics_attachments: Set[Sector] = set()
        self.execution_bindings: Dict[str, Sector] = {}
        self.safety_locks: Set[Sector] = set()
        self.pending_authorization: Dict[str, Sector] = {}
        self._authorized: Set[str] = set()
        self._calm_cycles = 0

    def process_cycle(self, telemetry: Dict[Sector, SectorMetrics], cycle_phase: Optional[str] = None):
        self.sector_state = telemetry
        # Reset per cycle, then rebuild from current telemetry + still-pending authorizations.
        self.safety_locks.clear()
        self.execution_bindings.clear()

        self._evaluate_safety_guardrails()
        self._evaluate_diagnostics_routing()
        self._update_battlefield_mode()
        self._update_threat_level()
        self._evaluate_coordinator_routing()

        if cycle_phase in ["morning", "midday", "evening", "night"]:
            self._run_optimization_pipeline()

    def authorize(self, task_id: str) -> bool:
        """Release a high-impact task so it may be dispatched.

        If the task is already queued or present in current telemetry, it is
        bound immediately. Otherwise it is marked authorized for a later cycle.
        """
        self._authorized.add(task_id)
        sector = self.pending_authorization.pop(task_id, None)
        if sector is None:
            for sec, metrics in self.sector_state.items():
                if task_id in metrics.active_tasks:
                    sector = sec
                    break
        if sector is not None:
            self.execution_bindings[task_id] = sector
            return True
        return True

    def release_execution_task(self, task_id: str):
        self.execution_bindings.pop(task_id, None)

    def _evaluate_safety_guardrails(self):
        for sector, metrics in self.sector_state.items():
            high_impact_actions = [t for t in metrics.active_tasks if is_high_impact(t)]
            if not high_impact_actions:
                continue
            self.safety_locks.add(Sector.CORE)
            if sector == Sector.EAST:
                self.safety_locks.add(Sector.EAST)
            for task in high_impact_actions:
                if task not in self._authorized:
                    self.pending_authorization[task] = sector
                else:
                    self._dispatch_execution(sector, task)

    def _anomalous_sectors(self) -> List[Sector]:
        anomalous: List[Sector] = []
        for sector, m in self.sector_state.items():
            if sector == Sector.NORTH and (m.jitter > 0.3 or m.drift > 0.3):
                anomalous.append(sector)
            elif sector == Sector.WEST and m.stagnation > 0.3:
                anomalous.append(sector)
            elif sector == Sector.SOUTH and (m.ghost_echoes or m.emotional_noise > 0.5):
                anomalous.append(sector)
        return anomalous

    def _evaluate_diagnostics_routing(self):
        self.diagnostics_attachments.clear()
        anomalous_sectors = self._anomalous_sectors()
        for sector in anomalous_sectors:
            self.diagnostics_attachments.add(sector)
        for active_sector in list(self.diagnostics_attachments):
            for neighbor in ADJACENCY_MAP[active_sector]:
                self.diagnostics_attachments.add(neighbor)

    def _update_battlefield_mode(self):
        anomalous_count = len(self._anomalous_sectors())
        if anomalous_count >= 3:
            self.global_battlefield_mode = True
            self._calm_cycles = 0
            return
        if anomalous_count < 2:
            self._calm_cycles += 1
            if self._calm_cycles >= self.hysteresis_cycles:
                self.global_battlefield_mode = False
        else:
            self._calm_cycles = 0

    def _inward_threat(self) -> bool:
        return any(m.inward_vector_to_core for m in self.sector_state.values())

    def _update_threat_level(self):
        # Threat follows current telemetry (anomaly count + inward vector),
        # independent of battlefield-mode hysteresis.
        anomalous_count = len(self._anomalous_sectors())
        inward = self._inward_threat()
        if inward and anomalous_count >= 3:
            self.threat_level = ThreatLevel.L5_GLOBAL_EMERGENCY
        elif inward:
            self.threat_level = ThreatLevel.L4_CRITICAL
        elif anomalous_count >= 3:
            self.threat_level = ThreatLevel.L3_HIGH
        elif anomalous_count == 2:
            self.threat_level = ThreatLevel.L2_ELEVATED
        elif anomalous_count == 1:
            self.threat_level = ThreatLevel.L1_NOMINAL
        else:
            self.threat_level = ThreatLevel.L0_STABLE

    def _evaluate_coordinator_routing(self):
        if self._inward_threat():
            self._dispatch_execution(Sector.CORE, "CORE_INWARD_INTERCEPT")
            self.safety_locks.add(Sector.CORE)
            return

        if self.global_battlefield_mode:
            self._dispatch_execution(Sector.CORE, "GLOBAL_DEFENSE_OVERRIDE")
            return

        if self.threat_level in [ThreatLevel.L0_STABLE, ThreatLevel.L1_NOMINAL]:
            primary_focus = [Sector.SOUTH, Sector.WEST]
        elif self.threat_level in [ThreatLevel.L2_ELEVATED, ThreatLevel.L3_HIGH]:
            primary_focus = [Sector.EAST, Sector.NORTH]
        else:
            primary_focus = [Sector.CORE, Sector.EAST]

        for sector in primary_focus:
            metrics = self.sector_state.get(sector)
            if not metrics or not metrics.active_tasks:
                continue
            for task in metrics.active_tasks:
                self._dispatch_execution(sector, task)

    def _dispatch_execution(self, sector: Sector, task_id: str):
        if is_high_impact(task_id) and task_id not in self._authorized:
            self.pending_authorization[task_id] = sector
            return
        self.execution_bindings[task_id] = sector

    def _run_optimization_pipeline(self):
        for sector in Sector:
            metrics = self.sector_state[sector]
            anomaly_score = metrics.jitter + metrics.drift + metrics.stagnation
            self.routing_weights.sector_weights[sector] = round(1.0 + anomaly_score, 2)
