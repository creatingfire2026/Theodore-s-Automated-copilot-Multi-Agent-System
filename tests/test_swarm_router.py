from swarm_router import AgentSwarmRouter, Sector, SectorMetrics, ThreatLevel


def idle_metrics():
    return {sector: SectorMetrics() for sector in Sector}


def with_metrics(overrides):
    state = idle_metrics()
    state.update(overrides)
    return state


def test_high_impact_tasks_wait_for_authorization():
    router = AgentSwarmRouter()
    router.process_cycle(
        with_metrics({
            Sector.EAST: SectorMetrics(active_tasks=["east_lockdown", "recon_sweep"]),
            Sector.SOUTH: SectorMetrics(active_tasks=["noise_filter"]),
        })
    )

    assert "east_lockdown" not in router.execution_bindings
    assert "east_lockdown" in router.pending_authorization
    assert router.pending_authorization["east_lockdown"] is Sector.EAST
    assert Sector.CORE in router.safety_locks
    assert Sector.EAST in router.safety_locks
    # Ordinary SOUTH/WEST tasks at L0 still dispatch.
    assert router.execution_bindings.get("noise_filter") is Sector.SOUTH

    router.authorize("east_lockdown")
    assert "east_lockdown" not in router.pending_authorization
    assert router.execution_bindings["east_lockdown"] is Sector.EAST

    # Authorization persists across cycles; bindings are rebuilt, not lost.
    router.process_cycle(
        with_metrics({Sector.EAST: SectorMetrics(active_tasks=["east_lockdown"])})
    )
    assert router.execution_bindings.get("east_lockdown") is Sector.EAST
    assert "east_lockdown" not in router.pending_authorization


def test_barrier_and_elite_also_require_authorization():
    router = AgentSwarmRouter()
    router.process_cycle(
        with_metrics({
            Sector.WEST: SectorMetrics(active_tasks=["raise_barrier", "elite_dispatch"]),
        })
    )
    assert "raise_barrier" not in router.execution_bindings
    assert "elite_dispatch" not in router.execution_bindings
    assert set(router.pending_authorization) == {"raise_barrier", "elite_dispatch"}
    router.authorize("raise_barrier")
    router.authorize("elite_dispatch")
    assert set(router.execution_bindings) >= {"raise_barrier", "elite_dispatch"}


def test_recovery_from_global_mode_uses_hysteresis_and_resets_locks():
    router = AgentSwarmRouter(hysteresis_cycles=2)
    storm = with_metrics({
        Sector.NORTH: SectorMetrics(jitter=0.8, drift=0.8, active_tasks=["perimeter_lockdown"]),
        Sector.WEST: SectorMetrics(stagnation=0.9),
        Sector.SOUTH: SectorMetrics(ghost_echoes=True, emotional_noise=0.9),
    })
    router.process_cycle(storm)
    assert router.global_battlefield_mode is True
    assert router.threat_level is ThreatLevel.L3_HIGH
    assert router.execution_bindings == {"GLOBAL_DEFENSE_OVERRIDE": Sector.CORE}
    assert "perimeter_lockdown" in router.pending_authorization
    locks_during_storm = set(router.safety_locks)
    assert Sector.CORE in locks_during_storm

    calm = idle_metrics()
    router.process_cycle(calm)
    # One calm cycle is not enough to exit (hysteresis=2).
    assert router.global_battlefield_mode is True
    assert router.execution_bindings == {"GLOBAL_DEFENSE_OVERRIDE": Sector.CORE}
    assert router.threat_level is ThreatLevel.L0_STABLE
    assert router.safety_locks == set()  # rebuilt from current telemetry, not accumulated

    router.process_cycle(calm)
    assert router.global_battlefield_mode is False
    assert "GLOBAL_DEFENSE_OVERRIDE" not in router.execution_bindings
    assert router.execution_bindings == {}
    assert router.safety_locks == set()
    assert router.threat_level is ThreatLevel.L0_STABLE


def test_execution_bindings_are_rebuilt_each_cycle():
    router = AgentSwarmRouter()
    router.process_cycle(with_metrics({Sector.SOUTH: SectorMetrics(active_tasks=["evac_route"])}))
    assert router.execution_bindings == {"evac_route": Sector.SOUTH}
    router.process_cycle(with_metrics({Sector.WEST: SectorMetrics(active_tasks=["convoy"])}))
    assert router.execution_bindings == {"convoy": Sector.WEST}
    assert "evac_route" not in router.execution_bindings


def test_threat_level_changes_with_anomaly_count_and_inward_vector():
    router = AgentSwarmRouter()
    router.process_cycle(idle_metrics())
    assert router.threat_level is ThreatLevel.L0_STABLE

    router.process_cycle(with_metrics({Sector.NORTH: SectorMetrics(jitter=0.5)}))
    assert router.threat_level is ThreatLevel.L1_NOMINAL

    router.process_cycle(
        with_metrics({
            Sector.NORTH: SectorMetrics(jitter=0.5),
            Sector.WEST: SectorMetrics(stagnation=0.5),
        })
    )
    assert router.threat_level is ThreatLevel.L2_ELEVATED
    assert router.global_battlefield_mode is False

    router.process_cycle(
        with_metrics({
            Sector.NORTH: SectorMetrics(jitter=0.5),
            Sector.WEST: SectorMetrics(stagnation=0.5),
            Sector.SOUTH: SectorMetrics(ghost_echoes=True),
        })
    )
    assert router.threat_level is ThreatLevel.L3_HIGH
    assert router.global_battlefield_mode is True

    router.process_cycle(
        with_metrics({Sector.EAST: SectorMetrics(inward_vector_to_core=True)})
    )
    assert router.threat_level is ThreatLevel.L4_CRITICAL

    router.process_cycle(
        with_metrics({
            Sector.NORTH: SectorMetrics(jitter=0.5, inward_vector_to_core=True),
            Sector.WEST: SectorMetrics(stagnation=0.5),
            Sector.SOUTH: SectorMetrics(ghost_echoes=True),
        })
    )
    assert router.threat_level is ThreatLevel.L5_GLOBAL_EMERGENCY


def test_inward_to_core_override():
    router = AgentSwarmRouter()
    router.process_cycle(
        with_metrics({
            Sector.NORTH: SectorMetrics(
                inward_vector_to_core=True,
                active_tasks=["recon_sweep"],
            ),
            Sector.SOUTH: SectorMetrics(active_tasks=["evac_route"]),
            Sector.WEST: SectorMetrics(active_tasks=["convoy"]),
        })
    )
    assert router.execution_bindings == {"CORE_INWARD_INTERCEPT": Sector.CORE}
    assert Sector.CORE in router.safety_locks
    assert router.threat_level is ThreatLevel.L4_CRITICAL
    # Local micro-routing is skipped for the inward override.
    assert "recon_sweep" not in router.execution_bindings
    assert "evac_route" not in router.execution_bindings
    assert "convoy" not in router.execution_bindings
