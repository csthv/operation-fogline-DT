"""
Operation Fogline plug-in workspace.

This file is the public implementation workspace imported by the simulator.
It intentionally contains API placeholders and guidance comments only. The
communication algorithms are expected to be implemented here while keeping the
function names, parameter order, and return types compatible with the API docs.

Do not edit simulator_core.py to work around missing implementation code here.
Add private helper functions in this file when they make your design clearer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import copy
import json

from simulator_core import (
    Department,
    ErrorControlMethod,
    Frame,
    MessageCategory,
    MissionMessage,
    MultiplexingMode,
    Priority,
    ProtectedFrame,
    ReceivedFrame,
    ReceiverDecision,
    RetransmissionDecision,
    ScenarioId,
    StrategyConfig,
    SystemState,
)

# ---------------------------------------------------------------------------
# Strategy configuration support
# ---------------------------------------------------------------------------
# These StrategyConfig entries are configuration shells for the dashboard. They
# do not perform frame construction, error protection, scheduling, receiver
# decisions, retransmission, or adaptation.

CUSTOM_STRATEGIES_PATH = Path(__file__).resolve().parent / "configs" / "custom_strategies.json"
CUSTOM_SCENARIO_GROUP = "custom_presets"


def _method_map(default: ErrorControlMethod = ErrorControlMethod.NONE) -> Dict[str, ErrorControlMethod]:
    """Create the StrategyConfig priority-to-method dictionary shape."""
    return {priority.value: default for priority in Priority}


def _category_method_map(default: ErrorControlMethod = ErrorControlMethod.NONE) -> Dict[str, ErrorControlMethod]:
    """Create the StrategyConfig category-to-method dictionary shape."""
    return {category.value: default for category in MessageCategory}


def _retry_limit_map(default: int = 0) -> Dict[str, int]:
    """Create the StrategyConfig priority-to-retry-limit dictionary shape."""
    return {priority.value: default for priority in Priority}


def _equal_department_share() -> Dict[str, float]:
    """Create a valid allocation dictionary for all departments."""
    share = 1.0 / len(Department)
    return {department.value: share for department in Department}


STRATEGIES: Dict[str, StrategyConfig] = {
    "starter_equal_tdm": StrategyConfig(
        name="starter_equal_tdm",
        description="Starter StrategyConfig shell using TDM mode.",
        multiplexing_mode=MultiplexingMode.TDM,
        error_control_by_priority=_method_map(),
        error_control_by_category=_category_method_map(),
        retransmission_limits_by_priority=_retry_limit_map(),
        receiver_strictness="normal",
        tdm_allocation=_equal_department_share(),
        fdm_allocation=_equal_department_share(),
        notes="Configuration shell. Implement module logic in student_modules.py.",
    ),
    "starter_priority_tdm": StrategyConfig(
        name="starter_priority_tdm",
        description="Starter StrategyConfig shell reserved for a priority-policy experiment.",
        multiplexing_mode=MultiplexingMode.TDM,
        error_control_by_priority=_method_map(),
        error_control_by_category=_category_method_map(),
        retransmission_limits_by_priority=_retry_limit_map(),
        receiver_strictness="normal",
        tdm_allocation=_equal_department_share(),
        fdm_allocation=_equal_department_share(),
        notes="Configuration shell. Fill in scheduling and priority policy yourself.",
    ),
    "starter_equal_fdm": StrategyConfig(
        name="starter_equal_fdm",
        description="Starter StrategyConfig shell using FDM mode.",
        multiplexing_mode=MultiplexingMode.FDM,
        error_control_by_priority=_method_map(),
        error_control_by_category=_category_method_map(),
        retransmission_limits_by_priority=_retry_limit_map(),
        receiver_strictness="normal",
        tdm_allocation=_equal_department_share(),
        fdm_allocation=_equal_department_share(),
        force_equal_fdm=True,
        notes="Configuration shell. Implement module logic in student_modules.py.",
    ),
}

STRATEGY_GROUPS: Dict[str, List[str]] = {
    ScenarioId.FIRST_FOG.value: ["starter_equal_tdm", "starter_priority_tdm", "starter_equal_fdm"],
    ScenarioId.ENEMY_LEARNS.value: ["starter_equal_tdm", "starter_priority_tdm", "starter_equal_fdm"],
    ScenarioId.BLACKOUT_HOUR.value: ["starter_equal_tdm", "starter_priority_tdm", "starter_equal_fdm"],
}


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def strategy_to_dict(strategy: StrategyConfig) -> Dict[str, Any]:
    """Serialize a StrategyConfig for dashboard-created custom presets."""
    return {
        "name": strategy.name,
        "description": strategy.description,
        "multiplexing_mode": _enum_value(strategy.multiplexing_mode),
        "error_control_by_priority": {k: _enum_value(v) for k, v in strategy.error_control_by_priority.items()},
        "error_control_by_category": {k: _enum_value(v) for k, v in strategy.error_control_by_category.items()},
        "retransmission_limits_by_priority": dict(strategy.retransmission_limits_by_priority),
        "receiver_strictness": strategy.receiver_strictness,
        "use_compact_emergency_mode": strategy.use_compact_emergency_mode,
        "suppress_routine_watchtower": strategy.suppress_routine_watchtower,
        "watchtower_reports_per_cycle_limit": strategy.watchtower_reports_per_cycle_limit,
        "tdm_allocation": dict(strategy.tdm_allocation),
        "fdm_allocation": dict(strategy.fdm_allocation),
        "avoid_slots": list(strategy.avoid_slots),
        "avoid_bands": list(strategy.avoid_bands),
        "auto_adapt": strategy.auto_adapt,
        "force_equal_fdm": strategy.force_equal_fdm,
        "notes": strategy.notes,
    }


def strategy_from_dict(data: Dict[str, Any]) -> StrategyConfig:
    """Load a dashboard-created StrategyConfig from a plain dictionary."""
    return StrategyConfig(
        name=str(data.get("name", "custom_strategy")),
        description=str(data.get("description", "Custom strategy")),
        multiplexing_mode=MultiplexingMode(data.get("multiplexing_mode", MultiplexingMode.TDM.value)),
        error_control_by_priority={k: ErrorControlMethod(v) for k, v in data.get("error_control_by_priority", _method_map()).items()},
        error_control_by_category={k: ErrorControlMethod(v) for k, v in data.get("error_control_by_category", _category_method_map()).items()},
        retransmission_limits_by_priority={k: int(v) for k, v in data.get("retransmission_limits_by_priority", _retry_limit_map()).items()},
        receiver_strictness=str(data.get("receiver_strictness", "normal")),
        use_compact_emergency_mode=bool(data.get("use_compact_emergency_mode", False)),
        suppress_routine_watchtower=bool(data.get("suppress_routine_watchtower", False)),
        watchtower_reports_per_cycle_limit=data.get("watchtower_reports_per_cycle_limit", None),
        tdm_allocation={k: float(v) for k, v in data.get("tdm_allocation", {}).items()},
        fdm_allocation={k: float(v) for k, v in data.get("fdm_allocation", {}).items()},
        avoid_slots=list(data.get("avoid_slots", [])),
        avoid_bands=list(data.get("avoid_bands", [])),
        auto_adapt=bool(data.get("auto_adapt", False)),
        force_equal_fdm=bool(data.get("force_equal_fdm", False)),
        notes=str(data.get("notes", "")),
    )


def load_custom_strategies() -> Dict[str, StrategyConfig]:
    """Load optional presets created by the dashboard preset wizard."""
    if not CUSTOM_STRATEGIES_PATH.exists():
        return {}
    try:
        payload = json.loads(CUSTOM_STRATEGIES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    loaded: Dict[str, StrategyConfig] = {}
    for name, data in payload.get("strategies", {}).items():
        try:
            loaded[name] = strategy_from_dict(data)
        except Exception:
            continue
    return loaded


def save_custom_strategy(strategy: StrategyConfig) -> Path:
    """Save a dashboard-created StrategyConfig."""
    CUSTOM_STRATEGIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"strategies": {}}
    if CUSTOM_STRATEGIES_PATH.exists():
        try:
            payload = json.loads(CUSTOM_STRATEGIES_PATH.read_text(encoding="utf-8"))
        except Exception:
            payload = {"strategies": {}}
    payload.setdefault("strategies", {})[strategy.name] = strategy_to_dict(strategy)
    CUSTOM_STRATEGIES_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return CUSTOM_STRATEGIES_PATH


def list_strategies() -> Dict[str, List[str]]:
    """Return available built-in and dashboard-created strategy names."""
    groups = copy.deepcopy(STRATEGY_GROUPS)
    custom = sorted(load_custom_strategies().keys())
    if custom:
        groups[CUSTOM_SCENARIO_GROUP] = custom
    return groups


def all_strategy_names() -> List[str]:
    """Return every known strategy name."""
    names = list(STRATEGIES.keys()) + list(load_custom_strategies().keys())
    return sorted(dict.fromkeys(names))


def get_strategy(strategy_name: str) -> StrategyConfig:
    """Return a copy of a named StrategyConfig."""
    if strategy_name in STRATEGIES:
        return copy.deepcopy(STRATEGIES[strategy_name])
    custom = load_custom_strategies()
    if strategy_name in custom:
        return copy.deepcopy(custom[strategy_name])
    raise KeyError(f"Unknown strategy: {strategy_name}")


# ---------------------------------------------------------------------------
# Required plug-in API placeholders
# ---------------------------------------------------------------------------
# Write the algorithm for each stage inside the matching function. Do not move
# these functions, rename them, or change their parameter lists.


def prepare_frame(message: MissionMessage, system_state: SystemState, strategy_config: StrategyConfig) -> Frame:
    """Build and return a simulator_core.Frame.

    Put frame-construction code here. Preserve message identity, source,
    destination, priority, category, payload bits, and enough header/sequence
    metadata for the later stages.
    """
    # TODO: Build and return a Frame instance here.
    raise NotImplementedError("prepare_frame must be implemented in student_modules.py")


def attach_error_control(frame: Frame, system_state: SystemState, strategy_config: StrategyConfig) -> ProtectedFrame:
    """Attach protection metadata and return a ProtectedFrame.

    Put encoder/protection code here. This function should report protected
    bits, overhead size, total transmitted size, and correction capability.
    """
    # TODO: Implement the protection scheme used by your design here.
    raise NotImplementedError("attach_error_control must be implemented in student_modules.py")


def verify_error_control(received_frame: ReceivedFrame, strategy_config: StrategyConfig) -> Dict[str, Any]:
    """Verify a received frame and return a verification dictionary.

    Put decoder/checker code here. The final receiver policy belongs in
    decide_received_frame(...), not in this function.
    """
    # TODO: Implement verification matching attach_error_control(...).
    raise NotImplementedError("verify_error_control must be implemented in student_modules.py")


def choose_multiplexing_plan(
    protected_frames: List[ProtectedFrame],
    system_state: SystemState,
    queue_state: Dict[str, Any],
    strategy_config: StrategyConfig,
) -> Dict[str, Any]:
    """Choose how protected frames use TDM slots or FDM bands.

    Put scheduling/resource-allocation code here. Decide what transmits now,
    what is deferred, and which resource each transmitted frame uses.
    """
    # TODO: Implement your TDM/FDM scheduling policy here.
    raise NotImplementedError("choose_multiplexing_plan must be implemented in student_modules.py")


def decide_received_frame(
    received_frame: ReceivedFrame,
    verification_result: Dict[str, Any],
    system_state: SystemState,
    strategy_config: StrategyConfig,
) -> ReceiverDecision:
    """Convert verification results into a receiver decision."""
    # TODO: Implement accept/reject/correct/retransmit-request logic here.
    raise NotImplementedError("decide_received_frame must be implemented in student_modules.py")


def decide_retransmission(
    frame_status: Dict[str, Any],
    message_context: MissionMessage,
    system_state: SystemState,
    strategy_config: StrategyConfig,
) -> RetransmissionDecision:
    """Decide what happens after a failed or uncertain transmission."""
    # TODO: Implement retry/defer/drop behavior here.
    raise NotImplementedError("decide_retransmission must be implemented in student_modules.py")


def adapt_strategy(
    dashboard_snapshot: Any,
    current_strategy_config: StrategyConfig,
    capabilities: Dict[str, Any],
) -> StrategyConfig:
    """Return the strategy configuration to use after an adaptation point."""
    # TODO: Implement adaptation only if your design uses it.
    raise NotImplementedError("adapt_strategy must be implemented in student_modules.py")


__all__ = [
    "STRATEGIES",
    "STRATEGY_GROUPS",
    "strategy_to_dict",
    "strategy_from_dict",
    "load_custom_strategies",
    "save_custom_strategy",
    "list_strategies",
    "all_strategy_names",
    "get_strategy",
    "prepare_frame",
    "attach_error_control",
    "verify_error_control",
    "choose_multiplexing_plan",
    "decide_received_frame",
    "decide_retransmission",
    "adapt_strategy",
]
