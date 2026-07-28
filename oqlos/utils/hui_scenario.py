"""Minimal HUI test scenario registered for connect-test test-hui page."""

from __future__ import annotations

import logging

from oqlos.core.state import StateManager
from oqlos.models.scenario import Goal, Scenario, Step

logger = logging.getLogger(__name__)


def register_hui_test_scenario(state_manager: StateManager) -> None:
    """Register ts-c20 so POST /api/v1/execution/step accepts test-hui manual actions."""
    if "ts-c20" in state_manager.scenarios:
        return

    hui_scenario = Scenario(
        id="ts-c20",
        name="HUI Test Scenario",
        description="Minimal scenario for HUI test page manual actions",
        device="hui-test-device",
        protocol="oql",
        goals=[
            Goal(
                id="goal-hui",
                name="HUI Actions",
                description="Manual HUI test actions",
                steps=[
                    Step(id="s1", action="SET", peripheral="head", value="deflate"),
                    Step(id="s2", action="SET", peripheral="head", value="inflate"),
                    Step(id="s3", action="SET", peripheral="mp_flow", value="+10"),
                    Step(id="s4", action="SET", peripheral="mp_flow", value="-10"),
                    Step(id="s5", action="SET", peripheral="lp_valve", value="bleed"),
                    Step(id="s6", action="SET", peripheral="sc_mode", value="press"),
                    Step(id="s7", action="SET", peripheral="sc_mode", value="bleed"),
                    Step(id="s8", action="SET", peripheral="wc_mode", value="press"),
                    Step(id="s9", action="SET", peripheral="wc_mode", value="bleed"),
                ],
                expectedResult="HUI actions executed",
                validationCriteria=[],
            )
        ],
    )
    state_manager.scenarios[hui_scenario.id] = hui_scenario
    logger.info("Registered HUI test scenario: %s", hui_scenario.id)
