"""
Operation Fogline Simulator Core
================================
A compact but complete simulator body for the Operation Fogline data-transmission
final project. The project intentionally uses a small number of Python files while
still exposing the documented architectural pieces: runtime, scenarios, live
events, departments, queues, frame pipeline, multiplexing, channel, receiver,
retransmission, metrics, dashboard, logs, and scoring summaries.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import copy
import csv
import importlib
import json
import math
import random
import time

from story_catalog import select_story_for_message


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Department(str, Enum):
    RADAR = "radar"
    WATCHTOWER = "watchtower"
    COMMAND = "command"


class MessageCategory(str, Enum):
    ROUTINE_REPORT = "routine_report"
    DETECTION_ALERT = "detection_alert"
    CONTROL_MESSAGE = "control_message"
    EMERGENCY_CODE = "emergency_code"
    MAINTENANCE = "maintenance"
    ACK = "ack"
    CORRECTION = "correction"
    WATCHTOWER_CRITICAL = "watchtower_critical"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorControlMethod(str, Enum):
    NONE = "none"
    PARITY = "parity"
    TWO_DIMENSIONAL_PARITY = "two_dimensional_parity"
    CHECKSUM16 = "checksum16"
    CRC16 = "crc16"
    CRC32 = "crc32"
    HAMMING_SECDED = "hamming_secded"


class MultiplexingMode(str, Enum):
    TDM = "tdm"
    FDM = "fdm"


class ReceiverStatus(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    CORRECTED = "corrected"
    AMBIGUOUS = "ambiguous"
    RETRANSMIT_REQUESTED = "retransmit_requested"
    INVALID_FRAME = "invalid_frame"


class ScenarioId(str, Enum):
    FIRST_FOG = "scenario_1_first_fog"
    ENEMY_LEARNS = "scenario_2_enemy_learns"
    BLACKOUT_HOUR = "scenario_3_blackout_hour"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MissionMessage:
    message_id: str
    source: Department
    destination: Department
    category: MessageCategory
    priority: Priority
    payload_bits: str
    payload_size_bits: int
    created_at_cycle: int
    deadline_cycle: int
    reliability_requirement: str
    retransmission_allowed: bool
    scenario_tag: str
    attempt: int = 0
    # Human-readable story overlay. These fields are optional and never replace
    # payload_bits; the technical simulator still transmits bits only.
    payload_text: str = ""
    story_role: str = "ordinary_chatter"
    observability: str = "none"
    linked_scenario_event: Optional[str] = None
    hint_strength: str = "none"
    misleading: bool = False
    scenario_note: str = ""
    story_template_id: str = ""


@dataclass
class Frame:
    frame_id: str
    message_id: str
    source: Department
    destination: Department
    category: MessageCategory
    priority: Priority
    sequence_number: int
    payload_bits: str
    payload_length_bits: int
    header_bits: str
    selected_error_control: ErrorControlMethod
    error_control_bits: str = ""
    retransmission_attempt: int = 0
    compact: bool = False


@dataclass
class ProtectedFrame:
    frame: Frame
    method: ErrorControlMethod
    protected_bits: str
    overhead_bits: int
    total_size_bits: int
    correction_capable: bool


@dataclass
class TransmissionUnit:
    protected_frame: ProtectedFrame
    multiplexing_mode: MultiplexingMode
    assigned_slot: Optional[str]
    assigned_band: Optional[str]
    scheduled_cycle: int
    resource_share_bits: int


@dataclass
class ReceivedFrame:
    frame_id: str
    message_id: str
    received_bits: str
    method: ErrorControlMethod
    arrival_cycle: int
    assigned_slot: Optional[str]
    assigned_band: Optional[str]
    visible_channel_flags: List[str]
    visible_frame: Frame


@dataclass
class HiddenChannelRecord:
    frame_id: str
    original_bits: str
    received_bits: str
    was_corrupted: bool
    corruption_type: str
    corrupted_bit_positions: List[int]
    original_payload_bits: str
    received_payload_bits_hint: Optional[str]


@dataclass
class ReceiverDecision:
    frame_id: str
    status: ReceiverStatus
    deliver_payload_bits: Optional[str]
    request_retransmission: bool
    confidence: str
    reason: str


@dataclass
class RetransmissionDecision:
    frame_id: str
    action: str
    strengthen_protection: bool
    delay_cycles: int
    reason: str


@dataclass
class StrategyConfig:
    name: str
    description: str
    multiplexing_mode: MultiplexingMode
    error_control_by_priority: Dict[str, ErrorControlMethod]
    error_control_by_category: Dict[str, ErrorControlMethod]
    retransmission_limits_by_priority: Dict[str, int]
    receiver_strictness: str = "normal"
    use_compact_emergency_mode: bool = False
    suppress_routine_watchtower: bool = False
    watchtower_reports_per_cycle_limit: Optional[int] = None
    tdm_allocation: Dict[str, float] = field(default_factory=dict)
    fdm_allocation: Dict[str, float] = field(default_factory=dict)
    avoid_slots: List[str] = field(default_factory=list)
    avoid_bands: List[str] = field(default_factory=list)
    auto_adapt: bool = False
    force_equal_fdm: bool = False
    notes: str = ""


@dataclass
class DashboardSnapshot:
    scenario_id: ScenarioId
    cycle: int
    phase: str
    active_event: Optional[str]
    estimated_bit_error_rate: float
    burst_error_indicator: float
    detected_error_count: int
    undetected_corruption_count: int
    accepted_incorrect_count: int
    rejected_frame_count: int
    corrected_frame_count: int
    retransmission_count: int
    average_delay_by_department: Dict[str, float]
    backlog_by_priority: Dict[str, int]
    backlog_by_department: Dict[str, int]
    link_utilization: float
    overhead_ratio: float
    available_capacity_bits: int
    current_strategy_name: str
    freeze_reason: Optional[str]


@dataclass
class LinkState:
    capacity_bits_per_cycle: int
    available_slots: List[str]
    unavailable_slots: List[str]
    available_bands: List[str]
    unavailable_bands: List[str]
    slot_capacity_bits: int
    band_capacity_bits: int
    bad_slot: Optional[str] = None
    bad_band: Optional[str] = None


@dataclass
class SystemState:
    scenario_id: ScenarioId
    cycle: int
    phase: str
    active_event: Optional[str]
    link_state: LinkState
    channel_profile: Dict[str, Any]
    visible_metrics: Dict[str, Any]


# ---------------------------------------------------------------------------
# Bit and simulator-shape helpers
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}


def enum_value(obj: Any) -> Any:
    """Convert enums nested inside dataclasses/lists/dicts into JSON values."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: enum_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [enum_value(v) for v in obj]
    return obj


def dataclass_to_json_dict(obj: Any) -> Dict[str, Any]:
    """Convert a simulator dataclass into a JSON-serializable dictionary."""
    return enum_value(asdict(obj))


def random_bits(rng: random.Random, length: int) -> str:
    """Generate random payload bits for the scenario message generator."""
    return "".join("1" if rng.random() < 0.5 else "0" for _ in range(length))


def flip_bit(bits: str, index: int) -> str:
    """Flip one bit for the simulator channel model."""
    if index < 0 or index >= len(bits):
        return bits
    new_bit = "0" if bits[index] == "1" else "1"
    return bits[:index] + new_bit + bits[index + 1:]


def int_to_bits(value: int, width: int) -> str:
    """Format an integer as a fixed-width binary string.

    This is a general simulator utility used by infrastructure code. It is not
    an error-control encoder or verifier.
    """
    return format(value & ((1 << width) - 1), f"0{width}b")


def overhead_for(method: ErrorControlMethod, compact_hamming: bool = False) -> int:
    """Return the expected protection-overhead size for public validation.

    The simulator exposes overhead constants because students need to return
    size-consistent ProtectedFrame objects. This function intentionally does not
    generate or verify any protection bits.
    """
    if method == ErrorControlMethod.NONE:
        return 0
    if method == ErrorControlMethod.PARITY:
        return 1
    if method == ErrorControlMethod.TWO_DIMENSIONAL_PARITY:
        return 16
    if method in (ErrorControlMethod.CHECKSUM16, ErrorControlMethod.CRC16):
        return 16
    if method == ErrorControlMethod.CRC32:
        return 32
    if method == ErrorControlMethod.HAMMING_SECDED:
        return 7 if compact_hamming else 7
    raise ValueError(f"Unsupported error control method: {method}")


# ---------------------------------------------------------------------------
# Config loading and scenario state
# ---------------------------------------------------------------------------

class ConfigLoader:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def load_scenario(self, scenario_id: ScenarioId) -> Dict[str, Any]:
        path = self.project_root / "configs" / "scenarios" / f"{scenario_id.value}.json"
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def load_grading(self) -> Dict[str, Any]:
        path = self.project_root / "configs" / "grading_config.json"
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)


class ScenarioEngine:
    def __init__(self, scenario_config: Dict[str, Any], rng: random.Random):
        self.config = scenario_config
        self.rng = rng
        self.event_schedule: Dict[int, str] = {}
        self._prepare_event_schedule()

    def _prepare_event_schedule(self) -> None:
        events = self.config.get("live_events", [])
        cycles = self.config.get("cycles", 40)
        if not events:
            return
        anchor_points = [max(2, int(cycles * ratio)) for ratio in (0.25, 0.45, 0.65, 0.80)]
        for i, event in enumerate(events[:4]):
            jitter = self.rng.randint(-2, 2)
            self.event_schedule[max(1, min(cycles - 1, anchor_points[i % len(anchor_points)] + jitter))] = event
        # Guarantee especially important events for the intended scenario lessons.
        sid = self.config["scenario_id"]
        if sid == ScenarioId.ENEMY_LEARNS.value:
            self.event_schedule[int(cycles * 0.35)] = "false_valid_frame"
        if sid == ScenarioId.BLACKOUT_HOUR.value:
            self.event_schedule[int(cycles * 0.30)] = "tdm_slot_group_lost"
            self.event_schedule[int(cycles * 0.55)] = "false_all_clear_risk"

    def get_phase(self, cycle: int) -> str:
        cycles = self.config.get("cycles", 40)
        pct = cycle / max(1, cycles)
        sid = self.config["scenario_id"]
        if sid == ScenarioId.FIRST_FOG.value:
            if pct < 0.25: return "calm_opening"
            if pct < 0.50: return "fog_thickens"
            if pct < 0.75: return "traffic_pressure"
            return "stabilized_baseline"
        if sid == ScenarioId.ENEMY_LEARNS.value:
            if pct < 0.25: return "suspicious_noise"
            if pct < 0.50: return "structured_interference"
            if pct < 0.75: return "silent_corruption_risk"
            return "counter_interference"
        if pct < 0.20: return "warning_signs"
        if pct < 0.35: return "pre_damage_alert"
        if pct < 0.60: return "communication_damage"
        if pct < 0.80: return "emergency_command_burst"
        return "survival_window"

    def active_event(self, cycle: int) -> Optional[str]:
        return self.event_schedule.get(cycle)

    def channel_profile_for(self, cycle: int, active_event: Optional[str]) -> Dict[str, Any]:
        base = copy.deepcopy(self.config.get("channel_profile", {}))
        sid = self.config["scenario_id"]
        phase = self.get_phase(cycle)
        if sid == ScenarioId.FIRST_FOG.value:
            if phase == "calm_opening":
                base["current_bit_error_rate"] = base.get("base_bit_error_rate", 0.0005)
            else:
                base["current_bit_error_rate"] = base.get("degraded_bit_error_rate", 0.001)
        else:
            base["current_bit_error_rate"] = base.get("base_bit_error_rate", 0.0008)
        if active_event in {"damp_cable_spike", "generator_flicker"}:
            base["current_bit_error_rate"] = base.get("current_bit_error_rate", 0.001) * 2.0
        if active_event in {"burst_jamming_pulse", "watchtower_repetition_flood", "damaged_line_retransmission_trap"}:
            base["burst_probability"] = max(base.get("burst_probability", 0.0), 0.10)
        if active_event == "false_valid_frame":
            base["force_false_valid_once"] = True
        if active_event == "false_all_clear_risk":
            base["force_false_valid_once"] = True
        return base

    def link_state_for(self, cycle: int, active_event: Optional[str]) -> LinkState:
        capacity = int(self.config.get("capacity_bits_per_cycle", 1200))
        if self.config["scenario_id"] == ScenarioId.BLACKOUT_HOUR.value:
            capacity = int(self.config.get("capacity_bits_per_cycle", 760))
        slots = [f"slot_{i}" for i in range(1, 11)]
        bands = ["band_a", "band_b", "band_c"]
        unavailable_slots: List[str] = []
        unavailable_bands: List[str] = []
        bad_slot = None
        bad_band = None
        if active_event == "slot_focused_interference":
            bad_slot = "slot_2"
        if active_event == "tdm_slot_group_lost":
            unavailable_slots = ["slot_8", "slot_9", "slot_10"]
            bad_slot = "slot_7"
        if active_event == "band_focused_interference":
            bad_band = "band_b"
        if active_event == "fdm_band_jammed":
            unavailable_bands = ["band_b"]
            bad_band = "band_b"
        available_slots = [s for s in slots if s not in unavailable_slots]
        available_bands = [b for b in bands if b not in unavailable_bands]
        slot_capacity = max(40, capacity // max(1, len(available_slots)))
        band_capacity = max(1, capacity // max(1, len(available_bands)))
        return LinkState(
            capacity_bits_per_cycle=capacity,
            available_slots=available_slots,
            unavailable_slots=unavailable_slots,
            available_bands=available_bands,
            unavailable_bands=unavailable_bands,
            slot_capacity_bits=slot_capacity,
            band_capacity_bits=band_capacity,
            bad_slot=bad_slot,
            bad_band=bad_band,
        )


# ---------------------------------------------------------------------------
# Departments and queue
# ---------------------------------------------------------------------------

class MessageGenerator:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.counter = 0

    def _make(self, cycle: int, source: Department, destination: Department, category: MessageCategory,
              priority: Priority, payload_size: int, scenario_tag: str, reliability: str,
              phase: Optional[str] = None, active_event: Optional[str] = None) -> MissionMessage:
        self.counter += 1
        deadline_delta = {
            Priority.LOW: 8,
            Priority.MEDIUM: 5,
            Priority.HIGH: 3,
            Priority.CRITICAL: 2,
        }[priority]
        payload_bits = random_bits(self.rng, payload_size)
        story = select_story_for_message(
            scenario_id=scenario_tag,
            cycle=cycle,
            source=source.value,
            destination=destination.value,
            category=category.value,
            priority=priority.value,
            counter=self.counter,
            phase=phase,
            active_event=active_event,
        )
        return MissionMessage(
            message_id=f"m{cycle:03d}_{self.counter:05d}",
            source=source,
            destination=destination,
            category=category,
            priority=priority,
            payload_bits=payload_bits,
            payload_size_bits=payload_size,
            created_at_cycle=cycle,
            deadline_cycle=cycle + deadline_delta,
            reliability_requirement=reliability,
            retransmission_allowed=priority != Priority.CRITICAL,
            scenario_tag=scenario_tag,
            payload_text=story.get("payload_text", ""),
            story_role=story.get("story_role", "ordinary_chatter"),
            observability=story.get("observability", "none"),
            linked_scenario_event=story.get("linked_scenario_event"),
            hint_strength=story.get("hint_strength", "none"),
            misleading=bool(story.get("misleading", False)),
            scenario_note=story.get("scenario_note", ""),
            story_template_id=story.get("story_template_id", ""),
        )

    def generate(self, scenario_config: Dict[str, Any], cycle: int, strategy: StrategyConfig, phase: Optional[str] = None, active_event: Optional[str] = None) -> List[MissionMessage]:
        sid = scenario_config["scenario_id"]
        messages: List[MissionMessage] = []
        if sid == ScenarioId.FIRST_FOG.value:
            sizes = scenario_config["payload_sizes_bits"]
            for _ in range(scenario_config["message_profile"].get("radar_alerts_per_cycle", 3)):
                messages.append(self._make(cycle, Department.RADAR, Department.COMMAND, MessageCategory.DETECTION_ALERT, Priority.HIGH, sizes["radar_alert"], sid, "very_low_error", phase, active_event))
            for _ in range(scenario_config["message_profile"].get("watchtower_reports_per_cycle", 2)):
                messages.append(self._make(cycle, Department.WATCHTOWER, Department.COMMAND, MessageCategory.ROUTINE_REPORT, Priority.LOW, sizes["watchtower_routine"], sid, "medium", phase, active_event))
            for _ in range(scenario_config["message_profile"].get("command_messages_per_cycle", 1)):
                messages.append(self._make(cycle, Department.COMMAND, Department.RADAR, MessageCategory.CONTROL_MESSAGE, Priority.HIGH, sizes["command_control"], sid, "very_low_error", phase, active_event))
        elif sid == ScenarioId.ENEMY_LEARNS.value:
            sizes = scenario_config["payload_sizes_bits"]
            for _ in range(scenario_config["message_profile"].get("radar_alerts_per_cycle", 4)):
                messages.append(self._make(cycle, Department.RADAR, Department.COMMAND, MessageCategory.DETECTION_ALERT, Priority.HIGH, sizes["radar_alert"], sid, "very_low_error", phase, active_event))
            wt_count = scenario_config["message_profile"].get("watchtower_reports_per_cycle", 2)
            if strategy.watchtower_reports_per_cycle_limit is not None:
                wt_count = min(wt_count, strategy.watchtower_reports_per_cycle_limit)
            for _ in range(wt_count):
                messages.append(self._make(cycle, Department.WATCHTOWER, Department.COMMAND, MessageCategory.ROUTINE_REPORT, Priority.MEDIUM, sizes["watchtower_routine"], sid, "medium", phase, active_event))
            for _ in range(scenario_config["message_profile"].get("command_messages_per_cycle", 2)):
                messages.append(self._make(cycle, Department.COMMAND, Department.RADAR, MessageCategory.CONTROL_MESSAGE, Priority.CRITICAL, sizes["command_control"], sid, "extremely_low_error", phase, active_event))
        else:
            sizes = scenario_config["payload_sizes_bits"]
            profile = scenario_config.get("message_profile", {})
            # Radar updates. Compact strategy uses compact payloads; others use normal radar size.
            radar_size = sizes["compact_radar_alert"] if strategy.use_compact_emergency_mode else sizes.get("radar_alert", 64)
            radar_count = int(profile.get("radar_alerts_per_cycle", 4))
            for _ in range(radar_count):
                messages.append(self._make(cycle, Department.RADAR, Department.COMMAND, MessageCategory.DETECTION_ALERT, Priority.HIGH, radar_size, sid, "very_low_error", phase, active_event))
            # Emergency codes and command control. Non-compact strategies treat codes as full control frames.
            if strategy.use_compact_emergency_mode:
                for _ in range(int(profile.get("command_emergency_codes_per_cycle", 2))):
                    messages.append(self._make(cycle, Department.COMMAND, Department.RADAR, MessageCategory.EMERGENCY_CODE, Priority.CRITICAL, sizes["command_emergency_code"], sid, "extremely_low_error", phase, active_event))
                for _ in range(int(profile.get("command_control_messages_per_cycle", 1))):
                    messages.append(self._make(cycle, Department.COMMAND, Department.WATCHTOWER, MessageCategory.CONTROL_MESSAGE, Priority.CRITICAL, sizes["command_control"], sid, "extremely_low_error", phase, active_event))
                for _ in range(int(profile.get("watchtower_critical_sightings_per_cycle", 1))):
                    messages.append(self._make(cycle, Department.WATCHTOWER, Department.COMMAND, MessageCategory.WATCHTOWER_CRITICAL, Priority.HIGH, sizes["compact_watchtower_critical"], sid, "very_low_error", phase, active_event))
            else:
                noncompact_command_count = int(profile.get("noncompact_command_messages_per_cycle", 3))
                for _ in range(noncompact_command_count):
                    messages.append(self._make(cycle, Department.COMMAND, Department.RADAR, MessageCategory.CONTROL_MESSAGE, Priority.CRITICAL, sizes["command_control"], sid, "extremely_low_error", phase, active_event))
                if not strategy.suppress_routine_watchtower:
                    for _ in range(int(profile.get("watchtower_routine_reports_per_cycle", 2))):
                        messages.append(self._make(cycle, Department.WATCHTOWER, Department.COMMAND, MessageCategory.ROUTINE_REPORT, Priority.LOW, sizes["watchtower_routine"], sid, "medium", phase, active_event))
        return messages


class MessageQueue:
    def __init__(self):
        self.pending: List[MissionMessage] = []
        self.dropped: List[MissionMessage] = []

    def add_many(self, messages: List[MissionMessage]) -> None:
        self.pending.extend(messages)

    def add(self, message: MissionMessage) -> None:
        self.pending.append(message)

    def remove_messages(self, message_ids: set[str]) -> None:
        self.pending = [m for m in self.pending if m.message_id not in message_ids]

    def expire_old(self, cycle: int) -> int:
        expired = [m for m in self.pending if m.deadline_cycle < cycle]
        self.dropped.extend(expired)
        self.pending = [m for m in self.pending if m.deadline_cycle >= cycle]
        return len(expired)

    def view(self) -> List[MissionMessage]:
        return list(self.pending)

    def backlog_by_priority(self) -> Dict[str, int]:
        out = {p.value: 0 for p in Priority}
        for m in self.pending:
            out[m.priority.value] += 1
        return out

    def backlog_by_department(self) -> Dict[str, int]:
        out = {d.value: 0 for d in Department}
        for m in self.pending:
            out[m.source.value] += 1
        return out


# ---------------------------------------------------------------------------
# Student module loader and adapter
# ---------------------------------------------------------------------------

class StudentModuleLoader:
    def __init__(self, module_name: str = "student_modules"):
        self.module_name = module_name
        self.module = importlib.import_module(module_name)

    def get_strategy(self, strategy_name: str) -> StrategyConfig:
        return self.module.get_strategy(strategy_name)

    def list_strategies(self) -> Dict[str, List[str]]:
        return self.module.list_strategies()

    def prepare_frame(self, message: MissionMessage, state: SystemState, strategy: StrategyConfig) -> Frame:
        return self.module.prepare_frame(message, state, strategy)

    def attach_error_control(self, frame: Frame, state: SystemState, strategy: StrategyConfig) -> ProtectedFrame:
        return self.module.attach_error_control(frame, state, strategy)

    def choose_multiplexing_plan(self, protected_frames: List[ProtectedFrame], state: SystemState, queue_state: Dict[str, Any], strategy: StrategyConfig) -> Dict[str, Any]:
        return self.module.choose_multiplexing_plan(protected_frames, state, queue_state, strategy)

    def verify_error_control(self, received_frame: ReceivedFrame, strategy: StrategyConfig) -> Dict[str, Any]:
        return self.module.verify_error_control(received_frame, strategy)

    def decide_received_frame(self, received_frame: ReceivedFrame, verification_result: Dict[str, Any], state: SystemState, strategy: StrategyConfig) -> ReceiverDecision:
        return self.module.decide_received_frame(received_frame, verification_result, state, strategy)

    def decide_retransmission(self, frame_status: Dict[str, Any], message_context: MissionMessage, state: SystemState, strategy: StrategyConfig) -> RetransmissionDecision:
        return self.module.decide_retransmission(frame_status, message_context, state, strategy)

    def adapt_strategy(self, dashboard_snapshot: DashboardSnapshot, current_strategy_config: StrategyConfig, capabilities: Dict[str, Any]) -> StrategyConfig:
        return self.module.adapt_strategy(dashboard_snapshot, current_strategy_config, capabilities)


class ValidationError(Exception):
    pass


class StudentAdapterValidator:
    @staticmethod
    def validate_frame(frame: Frame) -> None:
        if not frame.payload_bits or any(c not in "01" for c in frame.payload_bits):
            raise ValidationError("Frame payload must be a non-empty bit string.")
        if frame.payload_length_bits != len(frame.payload_bits):
            raise ValidationError("Frame payload length mismatch.")
        expected_header = 16 if frame.compact else 32
        if len(frame.header_bits) != expected_header:
            raise ValidationError(f"Header length must be {expected_header} bits.")

    @staticmethod
    def validate_protected(protected: ProtectedFrame) -> None:
        if protected.total_size_bits != len(protected.protected_bits):
            raise ValidationError("ProtectedFrame total size mismatch.")
        if any(c not in "01" for c in protected.protected_bits):
            raise ValidationError("Protected bits must be binary.")

    @staticmethod
    def validate_receiver_decision(decision: ReceiverDecision) -> None:
        if decision.status in (ReceiverStatus.ACCEPT, ReceiverStatus.CORRECTED) and decision.deliver_payload_bits is None:
            raise ValidationError("Accepted/corrected decision requires deliver_payload_bits.")


# ---------------------------------------------------------------------------
# Multiplexing validation and scheduling
# ---------------------------------------------------------------------------

class MultiplexingValidator:
    def validate_and_schedule(self, plan: Dict[str, Any], state: SystemState) -> Tuple[List[TransmissionUnit], List[str], int, int, List[str]]:
        transmissions: List[TransmissionUnit] = []
        deferred_ids: List[str] = []
        warnings: List[str] = []
        requested_bits = 0
        used_bits = 0
        capacity = state.link_state.capacity_bits_per_cycle
        mode = MultiplexingMode(plan.get("mode", state.link_state and MultiplexingMode.TDM))
        units = plan.get("units", [])
        if not isinstance(units, list):
            raise ValidationError("Multiplexing plan units must be a list.")
        band_used: Dict[str, int] = {b: 0 for b in state.link_state.available_bands}
        slot_used: Dict[str, int] = {s: 0 for s in state.link_state.available_slots}
        for item in units:
            pf = item["protected_frame"]
            requested_bits += pf.total_size_bits
            if item.get("deferred", False):
                deferred_ids.append(pf.frame.message_id)
                continue
            assigned_slot = item.get("assigned_slot")
            assigned_band = item.get("assigned_band")
            if mode == MultiplexingMode.TDM:
                if assigned_slot not in state.link_state.available_slots:
                    warnings.append(f"unavailable_slot:{assigned_slot}")
                    deferred_ids.append(pf.frame.message_id)
                    continue
                slot_used[assigned_slot] = slot_used.get(assigned_slot, 0) + pf.total_size_bits
            else:
                if assigned_band not in state.link_state.available_bands:
                    warnings.append(f"unavailable_band:{assigned_band}")
                    deferred_ids.append(pf.frame.message_id)
                    continue
                band_used[assigned_band] = band_used.get(assigned_band, 0) + pf.total_size_bits
                if band_used[assigned_band] > state.link_state.band_capacity_bits:
                    warnings.append(f"band_capacity_exceeded:{assigned_band}")
                    deferred_ids.append(pf.frame.message_id)
                    continue
            if used_bits + pf.total_size_bits > capacity:
                warnings.append("cycle_capacity_exceeded")
                deferred_ids.append(pf.frame.message_id)
                continue
            transmissions.append(TransmissionUnit(
                protected_frame=pf,
                multiplexing_mode=mode,
                assigned_slot=assigned_slot,
                assigned_band=assigned_band,
                scheduled_cycle=state.cycle,
                resource_share_bits=pf.total_size_bits,
            ))
            used_bits += pf.total_size_bits
        return transmissions, deferred_ids, used_bits, requested_bits, warnings


# ---------------------------------------------------------------------------
# Channel model
# ---------------------------------------------------------------------------

class ChannelModel:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.false_valid_consumed = False

    def transmit(self, unit: TransmissionUnit, state: SystemState) -> Tuple[ReceivedFrame, HiddenChannelRecord]:
        original_bits = unit.protected_frame.protected_bits
        bits = original_bits
        corruption_positions: List[int] = []
        flags: List[str] = []
        profile = state.channel_profile
        p = float(profile.get("current_bit_error_rate", profile.get("base_bit_error_rate", 0.0)))
        burst_probability = float(profile.get("burst_probability", 0.0))
        if unit.assigned_slot and unit.assigned_slot == state.link_state.bad_slot:
            p *= 4
            burst_probability = max(burst_probability, 0.15)
            flags.append("bad_tdm_slot")
        if unit.assigned_band and unit.assigned_band == state.link_state.bad_band:
            p *= 4
            burst_probability = max(burst_probability, 0.15)
            flags.append("bad_fdm_band")
        # Independent random bit flips.
        mutable = list(bits)
        for i, b in enumerate(mutable):
            if self.rng.random() < p:
                mutable[i] = "0" if b == "1" else "1"
                corruption_positions.append(i)
        bits = "".join(mutable)
        # Burst errors.
        if burst_probability > 0 and self.rng.random() < burst_probability and len(bits) >= 8:
            burst_len = self.rng.randint(4, min(24, len(bits)))
            start = self.rng.randint(0, len(bits) - burst_len)
            for i in range(start, start + burst_len):
                bits = flip_bit(bits, i)
                corruption_positions.append(i)
            flags.append("burst_error")
        # Structured interference event. The channel can inject correlated bit
        # changes for selected weak-protection labels, but it does not compute
        # or expose any protection-code arithmetic or reusable verifier logic.
        force_false = bool(profile.get("force_false_valid_once", False)) and not self.false_valid_consumed
        method = unit.protected_frame.method
        if force_false and method in (ErrorControlMethod.PARITY, ErrorControlMethod.CHECKSUM16):
            self.false_valid_consumed = True
            flags.append("structured_interference_risk")
            if len(bits) > 4:
                data_end = max(1, len(bits) - max(1, overhead_for(method)))
                first = self.rng.randint(0, max(0, data_end - 1))
                second = min(data_end - 1, first + 1)
                bits = flip_bit(flip_bit(bits, first), second)
                corruption_positions.extend([first, second])
        was_corrupted = bits != original_bits
        # Extract approximate received data bits for hidden comparison.
        received_hint = self._extract_data_bits(bits, method)
        received = ReceivedFrame(
            frame_id=unit.protected_frame.frame.frame_id,
            message_id=unit.protected_frame.frame.message_id,
            received_bits=bits,
            method=method,
            arrival_cycle=state.cycle,
            assigned_slot=unit.assigned_slot,
            assigned_band=unit.assigned_band,
            visible_channel_flags=flags,
            visible_frame=unit.protected_frame.frame,
        )
        hidden = HiddenChannelRecord(
            frame_id=unit.protected_frame.frame.frame_id,
            original_bits=original_bits,
            received_bits=bits,
            was_corrupted=was_corrupted,
            corruption_type="none" if not was_corrupted else ("structured" if "structured_false_valid_risk" in flags else "burst" if "burst_error" in flags else "random"),
            corrupted_bit_positions=sorted(set(corruption_positions)),
            original_payload_bits=unit.protected_frame.frame.payload_bits,
            received_payload_bits_hint=received_hint,
        )
        return received, hidden

    @staticmethod
    def _extract_data_bits(bits: str, method: ErrorControlMethod) -> Optional[str]:
        """Return a best-effort data-region hint for logs only.

        This helper deliberately does not decode or verify protection codes. The
        authoritative receiver decision must come from student_modules.py.
        """
        overhead = overhead_for(method)
        if overhead == 0 or len(bits) <= overhead:
            return bits
        return bits[:-overhead]


# ---------------------------------------------------------------------------
# Receiver, retransmission, metrics, dashboard, logging, grading
# ---------------------------------------------------------------------------

class MetricsEngine:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.generated_message_count = 0
        self.delivered_message_count = 0
        self.correct_delivery_count = 0
        self.accepted_incorrect_count = 0
        self.accepted_incorrect_critical = 0
        self.rejected_frame_count = 0
        self.corrected_frame_count = 0
        self.ambiguous_frame_count = 0
        self.retransmission_count = 0
        self.detected_error_count = 0
        self.undetected_corruption_count = 0
        self.deadline_miss_count = 0
        self.invalid_output_count = 0
        self.capacity_used_bits = 0
        self.capacity_requested_bits = 0
        self.capacity_available_bits = 1
        self.total_error_control_bits = 0
        self.total_transmitted_bits = 0
        self.delay_by_department: Dict[str, List[int]] = {d.value: [] for d in Department}
        self.delay_by_priority: Dict[str, List[int]] = {p.value: [] for p in Priority}
        self.slot_errors: Dict[str, int] = {}
        self.band_errors: Dict[str, int] = {}
        self.slot_attempts: Dict[str, int] = {}
        self.band_attempts: Dict[str, int] = {}
        self.cycles_survived = 0
        self.freeze_count = 0
        self.last_cycle_metrics: Dict[str, Any] = {}
        self.error_control_method_usage: Dict[str, int] = {m.value: 0 for m in ErrorControlMethod}
        self.multiplexing_mode_usage: Dict[str, int] = {m.value: 0 for m in MultiplexingMode}
        self.slot_usage: Dict[str, int] = {}
        self.band_usage: Dict[str, int] = {}
        self.deferred_message_count = 0
        self.deferred_cycle_count = 0

    def snapshot(self, scenario_id: ScenarioId, cycle: int, phase: str, active_event: Optional[str],
                 queue: MessageQueue, strategy: StrategyConfig, freeze_reason: Optional[str]) -> DashboardSnapshot:
        avg_dep = {k: (sum(v) / len(v) if v else 0.0) for k, v in self.delay_by_department.items()}
        utilization = self.capacity_requested_bits / max(1, self.capacity_available_bits)
        overhead_ratio = self.total_error_control_bits / max(1, self.total_transmitted_bits)
        return DashboardSnapshot(
            scenario_id=scenario_id,
            cycle=cycle,
            phase=phase,
            active_event=active_event,
            estimated_bit_error_rate=float(self.last_cycle_metrics.get("estimated_bit_error_rate", 0.0)),
            burst_error_indicator=float(self.last_cycle_metrics.get("burst_error_indicator", 0.0)),
            detected_error_count=self.detected_error_count,
            undetected_corruption_count=self.undetected_corruption_count,
            accepted_incorrect_count=self.accepted_incorrect_count,
            rejected_frame_count=self.rejected_frame_count,
            corrected_frame_count=self.corrected_frame_count,
            retransmission_count=self.retransmission_count,
            average_delay_by_department=avg_dep,
            backlog_by_priority=queue.backlog_by_priority(),
            backlog_by_department=queue.backlog_by_department(),
            link_utilization=utilization,
            overhead_ratio=overhead_ratio,
            available_capacity_bits=self.capacity_available_bits,
            current_strategy_name=strategy.name,
            freeze_reason=freeze_reason,
        )


class FreezePointManager:
    def __init__(self, thresholds: Dict[str, Any]):
        self.thresholds = thresholds
        self.frozen_reasons_seen: set[str] = set()

    def check(self, scenario_id: ScenarioId, metrics: MetricsEngine, snapshot: DashboardSnapshot) -> Optional[str]:
        t = self.thresholds
        # Avoid freezing every single cycle for the same reason; the log still records metrics.
        candidates: List[str] = []
        if snapshot.accepted_incorrect_count >= int(t.get("accepted_incorrect_count", 10**9)):
            candidates.append("accepted_incorrect_count")
        if metrics.accepted_incorrect_critical >= int(t.get("accepted_incorrect_critical", 10**9)):
            candidates.append("accepted_incorrect_critical")
        if snapshot.undetected_corruption_count >= int(t.get("undetected_corruption_count", 10**9)):
            candidates.append("undetected_corruption_count")
        if snapshot.link_utilization > float(t.get("link_utilization", 999.0)):
            candidates.append("link_utilization")
        if metrics.deadline_miss_count >= int(t.get("critical_deadline_miss", 10**9)):
            candidates.append("critical_deadline_miss")
        if metrics.invalid_output_count >= 3:
            candidates.append("repeated_invalid_student_output")
        detected_frame_error_rate = float(metrics.last_cycle_metrics.get("detected_frame_error_rate", 0.0))
        if detected_frame_error_rate > float(t.get("detected_error_rate", 999.0)):
            candidates.append("detected_error_rate")
        if scenario_id == ScenarioId.FIRST_FOG:
            wt_delay = snapshot.average_delay_by_department.get(Department.WATCHTOWER.value, 0.0)
            if wt_delay > float(t.get("watchtower_average_delay", 999.0)):
                candidates.append("watchtower_average_delay")
        if scenario_id == ScenarioId.ENEMY_LEARNS:
            slot_ratio_threshold = float(t.get("slot_error_ratio", 999.0))
            band_ratio_threshold = float(t.get("band_error_ratio", 999.0))
            slot_rates = [metrics.slot_errors.get(k, 0) / max(1, v) for k, v in metrics.slot_attempts.items() if k != "none"]
            band_rates = [metrics.band_errors.get(k, 0) / max(1, v) for k, v in metrics.band_attempts.items() if k != "none"]
            if slot_rates and max(slot_rates) > slot_ratio_threshold * (sum(slot_rates) / max(1, len(slot_rates))):
                candidates.append("slot_error_ratio")
            if band_rates and max(band_rates) > band_ratio_threshold * (sum(band_rates) / max(1, len(band_rates))):
                candidates.append("band_error_ratio")
        if scenario_id == ScenarioId.BLACKOUT_HOUR:
            critical_backlog = snapshot.backlog_by_priority.get(Priority.CRITICAL.value, 0)
            if critical_backlog > int(t.get("emergency_backlog_cycles", 999)):
                candidates.append("emergency_backlog")
            routine_share = float(metrics.last_cycle_metrics.get("routine_watchtower_capacity_share", 0.0))
            if routine_share > float(t.get("routine_watchtower_capacity_share", 999.0)):
                candidates.append("routine_watchtower_capacity_share")
        for reason in candidates:
            if reason not in self.frozen_reasons_seen:
                self.frozen_reasons_seen.add(reason)
                metrics.freeze_count += 1
                return reason
        return None


class RunLogger:
    def __init__(self, project_root: Path, run_id: str, scenario_id: ScenarioId,
                 strategy_name: str = "", seed: int | None = None, student_package: str = "student_modules"):
        self.project_root = project_root
        self.run_id = run_id
        self.scenario_id = scenario_id
        self.strategy_name = strategy_name
        self.seed = seed
        self.student_package = student_package
        self.cycles: List[Dict[str, Any]] = []
        self.project_root.joinpath("logs").mkdir(exist_ok=True)

    def log_cycle(self, entry: Dict[str, Any]) -> None:
        self.cycles.append(enum_value(entry))

    def save(self, final_metrics: Dict[str, Any], grading_summary: Dict[str, Any]) -> Tuple[Path, Path]:
        payload = {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id.value,
            "strategy_name": self.strategy_name,
            "student_package": self.student_package,
            "random_seed": self.seed,
            "cycles": self.cycles,
            "final_metrics": enum_value(final_metrics),
            "grading_summary": enum_value(grading_summary),
        }
        json_path = self.project_root / "logs" / f"{self.run_id}_{self.scenario_id.value}.json"
        csv_path = self.project_root / "logs" / f"{self.run_id}_{self.scenario_id.value}.csv"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        cols = [
            "run_id", "scenario_id", "cycle", "phase", "active_event", "strategy_name",
            "message_id", "frame_id", "created_at_cycle", "deadline_cycle", "source", "destination", "category", "priority",
            "payload_size_bits", "payload_bits", "payload_text", "story_role", "observability",
            "linked_scenario_event", "hint_strength", "misleading", "scenario_note", "story_template_id",
            "frame_size_bits", "error_control_method", "multiplexing_mode",
            "assigned_slot", "assigned_band", "was_corrupted", "corruption_type", "receiver_status",
            "accepted_correct", "accepted_incorrect", "retransmission_requested", "delay", "deadline_missed",
            "messages_generated", "frames_requested", "frames_transmitted", "capacity_requested_bits",
            "capacity_used_bits", "capacity_available_bits", "link_utilization", "accepted_incorrect_count",
            "rejected_frame_count", "corrected_frame_count", "retransmission_count", "deadline_miss_count",
            "detected_frame_error_rate", "routine_watchtower_capacity_share", "freeze_reason",
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            for c in self.cycles:
                metrics = c.get("metrics", {})
                common = {
                    "run_id": self.run_id,
                    "scenario_id": self.scenario_id.value,
                    "cycle": c.get("cycle"),
                    "phase": c.get("phase"),
                    "active_event": c.get("active_event"),
                    "strategy_name": c.get("strategy_name"),
                    "messages_generated": len(c.get("messages_generated", [])),
                    "frames_requested": c.get("frames_requested", 0),
                    "frames_transmitted": c.get("frames_transmitted", 0),
                    "capacity_requested_bits": metrics.get("capacity_requested_bits"),
                    "capacity_used_bits": metrics.get("capacity_used_bits"),
                    "capacity_available_bits": metrics.get("capacity_available_bits"),
                    "link_utilization": metrics.get("link_utilization"),
                    "accepted_incorrect_count": metrics.get("accepted_incorrect_count"),
                    "rejected_frame_count": metrics.get("rejected_frame_count"),
                    "corrected_frame_count": metrics.get("corrected_frame_count"),
                    "retransmission_count": metrics.get("retransmission_count"),
                    "deadline_miss_count": metrics.get("deadline_miss_count"),
                    "detected_frame_error_rate": metrics.get("detected_frame_error_rate"),
                    "routine_watchtower_capacity_share": metrics.get("routine_watchtower_capacity_share"),
                    "freeze_reason": c.get("freeze_reason"),
                }
                details = c.get("frames_transmitted_details", [])
                if not details:
                    writer.writerow(common)
                    continue
                for detail in details:
                    row = dict(common)
                    row.update(detail)
                    created = detail.get("created_at_cycle")
                    deadline = detail.get("deadline_cycle")
                    if created is not None:
                        row["delay"] = c.get("cycle", 0) - int(created)
                    if deadline is not None:
                        row["deadline_missed"] = c.get("cycle", 0) > int(deadline)
                    writer.writerow(row)
        return json_path, csv_path


class GradingEngine:
    """Convert run metrics into the implementation-document grading categories."""

    def grade(self, scenario_id: ScenarioId, metrics: MetricsEngine, cycles: int) -> Dict[str, Any]:
        generated = max(1, metrics.generated_message_count)
        delivered = max(0, metrics.delivered_message_count)
        correct = max(0, metrics.correct_delivery_count)
        delivery_ratio = correct / generated
        delivered_correct_ratio = correct / max(1, delivered)
        deadline_penalty_ratio = min(1.0, metrics.deadline_miss_count / max(1, generated))
        utilization = metrics.capacity_requested_bits / max(1, metrics.capacity_available_bits)
        overload = max(0.0, utilization - 1.0)
        retrans_pressure = metrics.retransmission_count / max(1, delivered)

        category_scores = {
            "correct_delivery": round(15 * delivery_ratio, 2),
            "silent_corruption_avoidance": round(max(0.0, 20 - metrics.accepted_incorrect_count * 12 - metrics.accepted_incorrect_critical * 18), 2),
            "priority_handling": round(max(0.0, 15 - metrics.accepted_incorrect_critical * 10 - metrics.deadline_miss_count * 0.08), 2),
            "delay_control": round(max(0.0, 10 * (1 - deadline_penalty_ratio)), 2),
            "error_control_appropriateness": round(max(0.0, 10 - metrics.undetected_corruption_count * 4 - metrics.accepted_incorrect_count * 4), 2),
            "retransmission_efficiency": round(max(0.0, 8 - retrans_pressure * 3), 2),
            "multiplexing_quality": round(max(0.0, 8 - overload * 12 - metrics.deadline_miss_count * 0.02), 2),
            "adaptability": round(max(0.0, 8 - max(0, metrics.freeze_count - 1) * 1.2), 2),
            "overhead_efficiency": round(max(0.0, 4 - max(0.0, metrics.total_error_control_bits / max(1, metrics.total_transmitted_bits) - 0.18) * 8), 2),
            "report_quality": 2.0,
        }
        raw_category_score = sum(category_scores.values())

        # Preserve the calibrated scenario ordering from the quantitative design while also exposing
        # a category-level breakdown. This keeps reference outcomes stable and transparent.
        calibrated_score = 100.0
        calibrated_score -= min(60, metrics.accepted_incorrect_count * 30)
        calibrated_score -= min(50, metrics.accepted_incorrect_critical * 30)
        calibrated_score -= min(60, metrics.deadline_miss_count * 0.30)
        calibrated_score -= min(20, overload * 35)
        calibrated_score -= min(10, metrics.invalid_output_count * 2)
        if scenario_id == ScenarioId.ENEMY_LEARNS and metrics.undetected_corruption_count > 0:
            calibrated_score -= 10
        if scenario_id == ScenarioId.BLACKOUT_HOUR and metrics.deadline_miss_count == 0 and metrics.accepted_incorrect_critical == 0:
            calibrated_score += 5
        calibrated_score = max(0.0, min(100.0, calibrated_score))

        return {
            "score": round(calibrated_score, 2),
            "category_scores": category_scores,
            "raw_category_score": round(raw_category_score, 2),
            "correct_delivery_count": metrics.correct_delivery_count,
            "delivered_message_count": metrics.delivered_message_count,
            "generated_message_count": metrics.generated_message_count,
            "accepted_incorrect_count": metrics.accepted_incorrect_count,
            "accepted_incorrect_critical": metrics.accepted_incorrect_critical,
            "deadline_miss_count": metrics.deadline_miss_count,
            "retransmission_count": metrics.retransmission_count,
            "cycles_survived": metrics.cycles_survived,
            "freeze_count": metrics.freeze_count,
            "link_utilization_last_cycle": round(utilization, 4),
            "delivered_correct_ratio": round(delivered_correct_ratio, 4),
        }




class InteractiveFreezeDashboard:
    """Console dashboard used at freeze points.

    It exposes the same StrategyConfig that the student modules consume, so
    students can change algorithms and policy knobs without touching simulator
    internals. It is intentionally text-based to keep the project dependency-free.
    """

    def __init__(self, loader: StudentModuleLoader, project_root: Path, scripted_commands: Optional[List[str]] = None):
        self.loader = loader
        self.project_root = project_root
        self.scripted_mode = scripted_commands is not None
        self.scripted_commands = list(scripted_commands or [])
        self.history: List[Dict[str, Any]] = []

    def _read_command(self, prompt: str) -> str:
        if self.scripted_commands:
            cmd = self.scripted_commands.pop(0).strip()
            print(f"{prompt}{cmd}")
            return cmd
        if self.scripted_mode:
            # Non-interactive/scripted runs should never block on stdin.
            cmd = "continue"
            print(f"{prompt}{cmd}")
            return cmd
        return input(prompt).strip()

    def _show(self, snapshot: DashboardSnapshot, state: SystemState, strategy: StrategyConfig) -> None:
        print("\n" + "=" * 86)
        print("OPERATION FOGLINE — INTERACTIVE FREEZE DASHBOARD")
        print("=" * 86)
        print(f"Scenario : {snapshot.scenario_id.value}")
        print(f"Cycle    : {snapshot.cycle}")
        print(f"Phase    : {snapshot.phase}")
        print(f"Event    : {snapshot.active_event or 'none'}")
        print(f"Freeze   : {snapshot.freeze_reason or 'none'}")
        print("-" * 86)
        print("Live link metrics")
        print(f"  Capacity      : {snapshot.available_capacity_bits} bits/cycle")
        print("                  Maximum amount of protected frame data the link can carry this cycle.")
        print(f"  Utilization   : {snapshot.link_utilization:.3f}")
        print("                  Requested bits / available capacity. Above 1.0 means backlog or deferral pressure.")
        print(f"  Overhead      : {snapshot.overhead_ratio:.3f}")
        print("                  Error-control bits / transmitted bits. High values mean stronger redundancy but less payload room.")
        print(f"  BER estimate  : {snapshot.estimated_bit_error_rate:.5f}")
        print("                  Observed bit-error fraction from the last cycle; useful for parity/checksum/CRC calculations.")
        print(f"  Burst index   : {snapshot.burst_error_indicator:.3f}")
        print("                  Fraction of transmitted frames hit by burst-like corruption in the last cycle.")
        print(f"  Detected errs : {snapshot.detected_error_count} | undetected={snapshot.undetected_corruption_count} | accepted_wrong={snapshot.accepted_incorrect_count}")
        print("                  Accepted-wrong is the most dangerous metric, especially for Radar and Command traffic.")
        print(f"  Frames        : rejected={snapshot.rejected_frame_count} corrected={snapshot.corrected_frame_count} retrans={snapshot.retransmission_count}")
        print("                  Rejections are safe failures; retransmissions improve reliability but consume capacity.")
        print(f"  Backlog       : priority={snapshot.backlog_by_priority} department={snapshot.backlog_by_department}")
        print("                  Shows which traffic classes are waiting because of errors, quotas, or capacity pressure.")
        print(f"  Delay         : {snapshot.average_delay_by_department}")
        print("                  Average delivered-message delay by source department, in simulation cycles.")
        print("-" * 86)
        print("Current strategy/configuration")
        print(f"  Strategy      : {strategy.name}")
        print(f"  Description   : {strategy.description}")
        print(f"  Multiplexing  : {strategy.multiplexing_mode.value} | receiver strictness={strategy.receiver_strictness}")
        print("                  TDM uses time slots; FDM uses bands. Strictness controls ambiguity rejection.")
        print(f"  Emergency     : compact={strategy.use_compact_emergency_mode} | suppress WT routine={strategy.suppress_routine_watchtower} | WT limit={strategy.watchtower_reports_per_cycle_limit}")
        print("                  Compact mode reduces emergency frame size; Watchtower shaping frees capacity.")
        print(f"  Avoid         : slots={strategy.avoid_slots or []} bands={strategy.avoid_bands or []}")
        print("                  Avoid lists keep critical traffic away from suspected damaged resources.")
        print(f"  TDM alloc     : {strategy.tdm_allocation}")
        print(f"  FDM alloc     : {strategy.fdm_allocation}")
        print("                  Allocation values are normalized into real per-department quotas and cannot exceed link capacity.")
        print("  EC/prio       : " + str({k: v.value for k, v in strategy.error_control_by_priority.items()}))
        print(f"  EC/category   : detection={strategy.error_control_by_category.get('detection_alert')} "
              f"control={strategy.error_control_by_category.get('control_message')} "
              f"emergency={strategy.error_control_by_category.get('emergency_code')} "
              f"routine={strategy.error_control_by_category.get('routine_report')}")
        print("-" * 86)
        print("Available resources")
        print("  TDM slots     : " + ",".join(state.link_state.available_slots) + f" | bad_slot={state.link_state.bad_slot} | slot_capacity={state.link_state.slot_capacity_bits} bits")
        print("  FDM bands     : " + ",".join(state.link_state.available_bands) + f" | bad_band={state.link_state.bad_band} | band_capacity={state.link_state.band_capacity_bits} bits")
        print("=" * 86)

    def _metric_explain(self) -> None:
        print("""
Metric explanations
===================
  Capacity: bits available in this simulation cycle.
  Utilization: requested bits divided by capacity. If it is above 1.0, the strategy is asking for more than the link can carry.
  Overhead ratio: error-control redundancy divided by transmitted bits. Stronger protection raises this number.
  BER estimate: observed bit-error fraction. Use it with P(corrupt)=1-(1-p)^n for frame calculations.
  Burst index: fraction of transmitted frames affected by burst-like interference.
  Detected errors: corrupted frames caught by the receiver/error-control logic.
  Undetected corruption: corrupted frames that slipped through verification.
  Accepted wrong: corrupted frames delivered as if valid. This is the most severe safety failure.
  Rejected frames: damaged/invalid frames rejected safely.
  Corrected frames: frames repaired by a correction method such as SECDED.
  Retransmissions: resend requests accepted by the retransmission module.
  Backlog: queued messages waiting for capacity, retransmission, or priority scheduling.
  Delay: delivered-message delay in simulation cycles.
  TDM/FDM allocation: normalized student weights converted into real capacity quotas.
""")

    def _print_strategy_list(self) -> List[str]:
        print("\nAvailable strategies and saved presets")
        print("=" * 78)
        all_names: List[str] = []
        for group, names in self.loader.list_strategies().items():
            print(f"{group}:")
            for name in names:
                all_names.append(name)
                print(f"  {len(all_names):2d}) {name}")
        print("=" * 78)
        return all_names

    def _choose_strategy_from_list(self, current: StrategyConfig) -> StrategyConfig:
        names = self._print_strategy_list()
        if not names:
            print("No strategies were found; keeping the current configuration.")
            return current
        raw = self._read_command("choose strategy number/name, or Enter to cancel> ")
        if not raw:
            print("Strategy unchanged.")
            return current
        selected = None
        if raw.isdigit() and 1 <= int(raw) <= len(names):
            selected = names[int(raw) - 1]
        elif raw in names:
            selected = raw
        if not selected:
            print("Unknown strategy; keeping current configuration.")
            return current
        chosen = self.loader.get_strategy(selected)
        chosen.auto_adapt = False
        print(f"Selected strategy: {chosen.name}")
        reply = self._read_command("Edit this selected preset before resuming? [yes/no, or continue to resume]> ")
        if self._yes(reply):
            chosen = self._guided_edit_current(chosen)
        return chosen

    def _help(self) -> None:
        print("""
Commands:
  show                                      redisplay dashboard
  explain / metrics                         explain dashboard metrics and what they mean
  presets / strategies                       list all preset/custom strategies
  choose                                    open numbered strategy selector
  use <strategy_name>                       switch current configuration to a preset
                                            then optionally step-by-step edit it before resuming
  wizard / edit                             step-by-step edit the current freeze configuration
  modules                                   show exposed module/policy choices
  set mux <tdm|fdm>                         switch multiplexing algorithm
  set priority <low|medium|high|critical> <method>
  set category <category_name> <method>     choose error control for a message category
  set strictness <normal|strict|very_strict>
  set compact <on|off>                      toggle compact emergency mode
  set suppress_watchtower <on|off>          toggle routine Watchtower suppression
  set watchtower_limit <none|0|1|2|...>
  set retransmit <priority> <attempts>
  set tdm_alloc <dept> <share>              set Radar/Watchtower/Command TDM share
  set fdm_alloc <dept> <share>              set Radar/Watchtower/Command FDM share
  normalize_alloc                           normalize allocation shares to sum to 1
  avoid slot <slot_id|none>                 avoid one TDM slot, or clear with none
  avoid band <band_id|none>                 avoid one FDM band, or clear with none
  save <custom_name>                        save current configuration as a reusable preset
  auto                                      call the adaptation module once
  continue                                  resume simulation with current configuration
""")

    def _modules(self) -> None:
        print("\nExposed student module controls:")
        print("  frame_module        : header mode changes through compact emergency mode")
        print("  error_control_module: none, parity, two_dimensional_parity, checksum16, crc16, crc32, hamming_secded")
        print("  multiplexing_module : tdm, fdm, allocation shares, avoided slots/bands")
        print("  receiver_module     : normal, strict, very_strict")
        print("  retransmission      : max attempts by priority")
        print("  adaptation_module   : callable through the 'auto' command")

    def _yes(self, value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "enable", "enabled", "edit"}

    def _choose_value(self, title: str, options: List[str], current: str) -> str:
        print("\n" + title)
        for idx, option in enumerate(options, 1):
            marker = " [current]" if option == current else ""
            print(f"  {idx}) {option}{marker}")
        raw = self._read_command("choose number/value or Enter to keep> ")
        if not raw:
            return current
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print("Invalid choice; keeping current value.")
        return current

    def _read_int(self, title: str, current: Optional[int], low: int, high: int, allow_none: bool = False) -> Optional[int]:
        shown = "none" if current is None else str(current)
        raw = self._read_command(f"{title} [{shown}] range {low}-{high}{' or none' if allow_none else ''}> ")
        if not raw:
            return current
        if allow_none and raw.lower() in {"none", "off", "clear"}:
            return None
        try:
            value = int(raw)
        except ValueError:
            print("Invalid integer; keeping current value.")
            return current
        if low <= value <= high:
            return value
        print("Out of range; keeping current value.")
        return current

    def _read_bool(self, title: str, current: bool) -> bool:
        raw = self._read_command(f"{title} [{'on' if current else 'off'}] yes/no> ")
        if not raw:
            return current
        lowered = raw.lower()
        if lowered in {"1", "true", "yes", "y", "on", "enable", "enabled"}:
            return True
        if lowered in {"0", "false", "no", "n", "off", "disable", "disabled"}:
            return False
        print("Invalid boolean; keeping current value.")
        return current

    def _edit_alloc(self, label: str, alloc: Dict[str, float]) -> Dict[str, float]:
        print(f"\n{label} allocation shares")
        print("  Enter non-negative weights for radar/watchtower/command. The system normalizes them automatically.")
        base = {"radar": 1/3, "watchtower": 1/3, "command": 1/3}
        base.update({k: float(v) for k, v in (alloc or {}).items() if k in base})
        out = {}
        for dept in ["radar", "watchtower", "command"]:
            raw = self._read_command(f"{dept} weight [{base[dept]:.3f}] range 0.0-10.0> ")
            if not raw:
                value = base[dept]
            else:
                try:
                    value = float(raw)
                except ValueError:
                    print("Invalid number; keeping current value for this department.")
                    value = base[dept]
            if value < 0 or value > 10:
                print("Out of range; keeping current value for this department.")
                value = base[dept]
            out[dept] = value
        total = sum(out.values())
        if total <= 0:
            print("Total allocation was zero; keeping equal shares.")
            return base
        normalized = {k: v / total for k, v in out.items()}
        print("  Normalized:", {k: round(v, 4) for k, v in normalized.items()})
        return normalized

    def _normalize_allocation(self, alloc: Dict[str, float]) -> Dict[str, float]:
        base = {"radar": 1/3, "watchtower": 1/3, "command": 1/3}
        cleaned = {}
        for dept in base:
            try:
                cleaned[dept] = min(10.0, max(0.0, float((alloc or {}).get(dept, base[dept]))))
            except (TypeError, ValueError):
                cleaned[dept] = base[dept]
        total = sum(cleaned.values())
        if total <= 0:
            return base
        return {dept: value / total for dept, value in cleaned.items()}

    def _guided_edit_current(self, current: StrategyConfig) -> StrategyConfig:
        print("\nStep-by-step freeze configuration editor")
        print("=" * 78)
        print("Each step shows the current value and allowed modes/ranges. Press Enter to keep a value.")
        edited = copy.deepcopy(current)
        edited.multiplexing_mode = MultiplexingMode(self._choose_value("1) Multiplexing mode: changes how frames share the link.", [m.value for m in MultiplexingMode], edited.multiplexing_mode.value))
        edited.receiver_strictness = self._choose_value("2) Receiver strictness: controls how suspicious/ambiguous frames are handled.", ["normal", "strict", "very_strict"], edited.receiver_strictness)
        methods = [m.value for m in ErrorControlMethod]
        print("\n3) Error control by priority: changes redundancy/detection for low/medium/high/critical traffic.")
        for pr in [p.value for p in Priority]:
            current_method = edited.error_control_by_priority.get(pr, ErrorControlMethod.CRC16).value
            edited.error_control_by_priority[pr] = ErrorControlMethod(self._choose_value(f"priority {pr}", methods, current_method))
        print("\n4) Error control by important category: lets emergency/control/detection/routine traffic use different methods.")
        for cat in [MessageCategory.DETECTION_ALERT.value, MessageCategory.CONTROL_MESSAGE.value, MessageCategory.EMERGENCY_CODE.value, MessageCategory.ROUTINE_REPORT.value]:
            current_method = edited.error_control_by_category.get(cat, ErrorControlMethod.CRC16).value
            edited.error_control_by_category[cat] = ErrorControlMethod(self._choose_value(f"category {cat}", methods, current_method))
        print("\n5) Retransmission limits by priority: prevents or allows retries. Range 0-5 attempts.")
        for pr in [p.value for p in Priority]:
            edited.retransmission_limits_by_priority[pr] = int(self._read_int(f"max attempts for {pr}", int(edited.retransmission_limits_by_priority.get(pr, 1)), 0, 5) or 0)
        edited.use_compact_emergency_mode = self._read_bool("6) Compact emergency mode: use shorter emergency payloads when capacity is tight", edited.use_compact_emergency_mode)
        edited.suppress_routine_watchtower = self._read_bool("7) Suppress routine Watchtower traffic: frees capacity for Radar/Command", edited.suppress_routine_watchtower)
        edited.watchtower_reports_per_cycle_limit = self._read_int("8) Watchtower reports per cycle limit", edited.watchtower_reports_per_cycle_limit, 0, 5, allow_none=True)
        edited.tdm_allocation = self._edit_alloc("9) TDM", edited.tdm_allocation)
        edited.fdm_allocation = self._edit_alloc("10) FDM", edited.fdm_allocation)
        raw_slots = self._read_command(f"11) Avoid TDM slots, comma-separated slot_1..slot_10 or none [{','.join(edited.avoid_slots) if edited.avoid_slots else 'none'}]> ")
        if raw_slots:
            edited.avoid_slots = [] if raw_slots.lower() in {"none", "clear", "off"} else [v.strip() for v in raw_slots.split(",") if v.strip()]
        raw_bands = self._read_command(f"12) Avoid FDM bands, comma-separated band_a/band_b/band_c or none [{','.join(edited.avoid_bands) if edited.avoid_bands else 'none'}]> ")
        if raw_bands:
            edited.avoid_bands = [] if raw_bands.lower() in {"none", "clear", "off"} else [v.strip() for v in raw_bands.split(",") if v.strip()]
        edited.name = edited.name + "_freeze_edit" if not edited.name.endswith("_freeze_edit") else edited.name
        print("\nEdited freeze-time configuration ready:")
        print(f"  strategy={edited.name} mux={edited.multiplexing_mode.value} strictness={edited.receiver_strictness}")
        print(f"  compact={edited.use_compact_emergency_mode} suppress_watchtower={edited.suppress_routine_watchtower}")
        return edited

    def edit(self, snapshot: DashboardSnapshot, state: SystemState, strategy: StrategyConfig) -> StrategyConfig:
        current = copy.deepcopy(strategy)
        current.auto_adapt = False
        self._show(snapshot, state, current)
        self._help()
        while True:
            cmd = self._read_command("fogline-freeze> ")
            if not cmd:
                continue
            parts = cmd.split()
            action = parts[0].lower()
            try:
                if action == "help":
                    self._help()
                elif action == "show":
                    self._show(snapshot, state, current)
                elif action == "modules":
                    self._modules()
                elif action in {"explain", "metrics"}:
                    self._metric_explain()
                elif action in {"presets", "strategies", "list"}:
                    self._print_strategy_list()
                elif action in {"choose", "select", "strategy"}:
                    current = self._choose_strategy_from_list(current)
                    reply = self._read_command("Resume now with this configuration? [yes/no]> ")
                    if self._yes(reply):
                        self.history.append({"cycle": snapshot.cycle, "freeze_reason": snapshot.freeze_reason, "strategy_after": current.name})
                        return current
                elif action == "use" and len(parts) >= 2:
                    current = self.loader.get_strategy(parts[1])
                    current.auto_adapt = False
                    print(f"Switched to preset: {current.name}")
                    reply = self._read_command("Edit this selected preset before resuming? [yes/no, or continue to resume]> ")
                    if reply.lower() in {"continue", "c", "resume"}:
                        self.history.append({"cycle": snapshot.cycle, "freeze_reason": snapshot.freeze_reason, "strategy_after": current.name})
                        return current
                    if self._yes(reply):
                        current = self._guided_edit_current(current)
                elif action == "set" and len(parts) >= 3:
                    target = parts[1].lower()
                    if target == "mux":
                        current.multiplexing_mode = MultiplexingMode(parts[2].lower())
                    elif target == "priority" and len(parts) >= 4:
                        current.error_control_by_priority[parts[2].lower()] = ErrorControlMethod(parts[3].lower())
                    elif target == "category" and len(parts) >= 4:
                        current.error_control_by_category[parts[2].lower()] = ErrorControlMethod(parts[3].lower())
                    elif target == "strictness":
                        if parts[2] not in {"normal", "strict", "very_strict"}:
                            raise ValueError("strictness must be normal, strict, or very_strict")
                        current.receiver_strictness = parts[2]
                    elif target == "compact":
                        current.use_compact_emergency_mode = parts[2].lower() in {"on", "true", "yes", "1"}
                    elif target == "suppress_watchtower":
                        current.suppress_routine_watchtower = parts[2].lower() in {"on", "true", "yes", "1"}
                    elif target == "watchtower_limit":
                        current.watchtower_reports_per_cycle_limit = None if parts[2].lower() == "none" else int(parts[2])
                    elif target == "retransmit" and len(parts) >= 4:
                        current.retransmission_limits_by_priority[parts[2].lower()] = int(parts[3])
                    elif target in {"tdm_alloc", "fdm_alloc"} and len(parts) >= 4:
                        dept = parts[2].lower()
                        if dept not in {"radar", "watchtower", "command"}:
                            raise ValueError("department must be radar, watchtower, or command")
                        share = float(parts[3])
                        if not 0.0 <= share <= 10.0:
                            raise ValueError("allocation weight must be between 0.0 and 10.0")
                        alloc = current.tdm_allocation if target == "tdm_alloc" else current.fdm_allocation
                        if not alloc:
                            alloc.update({"radar": 1/3, "watchtower": 1/3, "command": 1/3})
                        alloc[dept] = share
                        print(f"Set {target} {dept} weight={share}. Runtime scheduling normalizes allocation so quotas never exceed available capacity.")
                    else:
                        print("Unknown set command. Type help.")
                elif action == "normalize_alloc":
                    current.tdm_allocation = self._normalize_allocation(current.tdm_allocation)
                    current.fdm_allocation = self._normalize_allocation(current.fdm_allocation)
                    print("Normalized TDM/FDM allocation shares.")
                elif action == "avoid" and len(parts) >= 3:
                    kind = parts[1].lower()
                    value = parts[2]
                    if kind == "slot":
                        current.avoid_slots = [] if value.lower() == "none" else [value]
                    elif kind == "band":
                        current.avoid_bands = [] if value.lower() == "none" else [value]
                    else:
                        print("Use: avoid slot <slot|none> or avoid band <band|none>")
                elif action == "save" and len(parts) >= 2:
                    import student_modules
                    current.name = parts[1]
                    current.description = current.description or "Custom preset saved from interactive dashboard."
                    path = student_modules.save_custom_strategy(current)
                    print(f"Saved custom preset '{current.name}' to {path}")
                elif action in {"wizard", "edit", "guided_edit"}:
                    current = self._guided_edit_current(current)
                elif action == "auto":
                    current = self.loader.adapt_strategy(snapshot, current, {"all_methods": [m.value for m in ErrorControlMethod]})
                    current.auto_adapt = False
                    print(f"Adaptation module selected: {current.name}")
                    reply = self._read_command("Edit the auto-selected configuration before resuming? [yes/no, or continue to resume]> ")
                    if reply.lower() in {"continue", "c", "resume"}:
                        self.history.append({"cycle": snapshot.cycle, "freeze_reason": snapshot.freeze_reason, "strategy_after": current.name})
                        return current
                    if self._yes(reply):
                        current = self._guided_edit_current(current)
                elif action in {"continue", "c", "resume"}:
                    self.history.append({"cycle": snapshot.cycle, "freeze_reason": snapshot.freeze_reason, "strategy_after": current.name})
                    return current
                else:
                    print("Unknown command. Type help.")
            except Exception as exc:
                print(f"Command failed: {exc}")

# ---------------------------------------------------------------------------
# Runtime controller
# ---------------------------------------------------------------------------

class SimulationRuntime:
    def __init__(self, project_root: Path, scenario_id: ScenarioId, strategy_name: str,
                 seed: int = 42, student_module: str = "student_modules", quiet: bool = False,
                 auto_adapt: bool = False, interactive_freeze: bool = False,
                 interactive_script: Optional[List[str]] = None,
                 strategy_override: Optional[StrategyConfig] = None, save_logs: bool = True,
                 cycle_limit: Optional[int] = None, max_pending_messages: Optional[int] = None,
                 cycle_dashboard: bool = False, cycle_script: Optional[List[str]] = None,
                 manual_freeze_enabled: bool = True):
        self.project_root = project_root
        self.scenario_id = scenario_id
        self.strategy_name = strategy_name
        self.seed = seed
        self.rng = random.Random(seed)
        self.quiet = quiet
        self.auto_adapt = auto_adapt
        self.interactive_freeze = interactive_freeze
        self.cycle_dashboard = cycle_dashboard
        self.manual_freeze_enabled = manual_freeze_enabled
        self.cycle_scripted_mode = cycle_script is not None
        self.cycle_script = list(cycle_script or [])
        self.loader = StudentModuleLoader(student_module)
        self.strategy = copy.deepcopy(strategy_override) if strategy_override is not None else self.loader.get_strategy(strategy_name)
        self.strategy_name = self.strategy.name
        if auto_adapt:
            self.strategy.auto_adapt = True
        self.config_loader = ConfigLoader(project_root)
        self.scenario_config = self.config_loader.load_scenario(scenario_id)
        self.scenario_engine = ScenarioEngine(self.scenario_config, self.rng)
        self.message_generator = MessageGenerator(self.rng)
        self.queue = MessageQueue()
        self.channel = ChannelModel(self.rng)
        self.metrics = MetricsEngine()
        self.freeze_manager = FreezePointManager(self.scenario_config.get("freeze_thresholds", {}))
        self.grading = GradingEngine()
        self.validator = MultiplexingValidator()
        self.save_logs = save_logs
        run_id = f"run_{int(time.time())}_{self.strategy.name}_{seed}"
        self.logger = RunLogger(project_root, run_id, scenario_id, strategy_name=self.strategy.name, seed=seed, student_package=student_module) if save_logs else None
        self.interactive_dashboard = InteractiveFreezeDashboard(self.loader, project_root, interactive_script) if (interactive_freeze or (cycle_dashboard and manual_freeze_enabled)) else None
        self.interactive_events: List[Dict[str, Any]] = []
        self.sequence_counter = 0
        self.message_by_id: Dict[str, MissionMessage] = {}
        self.cycle_limit = cycle_limit
        self.max_pending_messages = max_pending_messages

    def _build_system_state(self, cycle: int, phase: str, active_event: Optional[str], link_state: LinkState, channel_profile: Dict[str, Any]) -> SystemState:
        visible_metrics = {
            "accepted_incorrect_count": self.metrics.accepted_incorrect_count,
            "retransmission_count": self.metrics.retransmission_count,
            "deadline_miss_count": self.metrics.deadline_miss_count,
        }
        return SystemState(self.scenario_id, cycle, phase, active_event, link_state, channel_profile, visible_metrics)

    def _prepare_frames(self, messages: List[MissionMessage], state: SystemState) -> List[ProtectedFrame]:
        protected_frames: List[ProtectedFrame] = []
        for message in messages:
            try:
                frame = self.loader.prepare_frame(message, state, self.strategy)
                self.sequence_counter += 1
                # Student function can set sequence itself; keep if present.
                StudentAdapterValidator.validate_frame(frame)
                protected = self.loader.attach_error_control(frame, state, self.strategy)
                StudentAdapterValidator.validate_protected(protected)
                protected_frames.append(protected)
                self.metrics.total_error_control_bits += protected.overhead_bits
            except Exception as exc:
                self.metrics.invalid_output_count += 1
                if not self.quiet:
                    print(f"[validation-warning] message={message.message_id}: {exc}")
        return protected_frames

    def _process_receiver(self, received: ReceivedFrame, hidden: HiddenChannelRecord, state: SystemState) -> Tuple[Optional[ReceiverDecision], bool, bool]:
        message = self.message_by_id.get(received.message_id)
        if message is None:
            return None, False, False
        try:
            verification = self.loader.verify_error_control(received, self.strategy)
            decision = self.loader.decide_received_frame(received, verification, state, self.strategy)
            StudentAdapterValidator.validate_receiver_decision(decision)
        except Exception as exc:
            self.metrics.invalid_output_count += 1
            if not self.quiet:
                print(f"[receiver-warning] frame={received.frame_id}: {exc}")
            return None, False, False
        was_delivered = False
        accepted_wrong = False
        if hidden.was_corrupted and decision.status in (ReceiverStatus.REJECT, ReceiverStatus.RETRANSMIT_REQUESTED, ReceiverStatus.AMBIGUOUS, ReceiverStatus.INVALID_FRAME):
            self.metrics.detected_error_count += 1
        if decision.status == ReceiverStatus.REJECT:
            self.metrics.rejected_frame_count += 1
        if decision.status == ReceiverStatus.AMBIGUOUS:
            self.metrics.ambiguous_frame_count += 1
            self.metrics.rejected_frame_count += 1
        if decision.status == ReceiverStatus.CORRECTED:
            self.metrics.corrected_frame_count += 1
        if decision.status in (ReceiverStatus.ACCEPT, ReceiverStatus.CORRECTED):
            delivered_payload = decision.deliver_payload_bits or ""
            # Data bits include header+payload for standard methods; compare suffix with original payload.
            correct = delivered_payload.endswith(hidden.original_payload_bits)
            self.metrics.delivered_message_count += 1
            was_delivered = True
            delay = state.cycle - message.created_at_cycle
            self.metrics.delay_by_department[message.source.value].append(delay)
            self.metrics.delay_by_priority[message.priority.value].append(delay)
            if state.cycle > message.deadline_cycle:
                self.metrics.deadline_miss_count += 1
            if correct:
                self.metrics.correct_delivery_count += 1
            else:
                accepted_wrong = True
                self.metrics.accepted_incorrect_count += 1
                self.metrics.undetected_corruption_count += 1
                if message.priority in (Priority.HIGH, Priority.CRITICAL) or message.source in (Department.RADAR, Department.COMMAND):
                    self.metrics.accepted_incorrect_critical += 1
        if decision.request_retransmission and not was_delivered:
            try:
                rdec = self.loader.decide_retransmission({"receiver_decision": decision, "attempt": message.attempt}, message, state, self.strategy)
                if rdec.action in ("retransmit_now", "retransmit_later"):
                    limit = self.strategy.retransmission_limits_by_priority.get(message.priority.value, 0)
                    if message.attempt < limit and state.cycle <= message.deadline_cycle:
                        new_msg = copy.deepcopy(message)
                        new_msg.attempt += 1
                        new_msg.message_id = f"{message.message_id}_rt{new_msg.attempt}"
                        self.message_by_id[new_msg.message_id] = new_msg
                        self.queue.add(new_msg)
                        self.metrics.retransmission_count += 1
                elif rdec.action == "drop_message":
                    self.queue.dropped.append(message)
            except Exception:
                self.metrics.invalid_output_count += 1
        return decision, was_delivered, accepted_wrong

    def _short_bits(self, bits: str, *, head: int = 64, tail: int = 16) -> str:
        if len(bits) <= head + tail + 8:
            return bits
        return f"{bits[:head]}...{bits[-tail:]}"

    def _message_label(self, message: MissionMessage) -> str:
        labels = {
            MessageCategory.DETECTION_ALERT: "Radar detection alert",
            MessageCategory.ROUTINE_REPORT: "Watchtower routine report",
            MessageCategory.CONTROL_MESSAGE: "Command control message",
            MessageCategory.EMERGENCY_CODE: "Compact emergency code",
            MessageCategory.MAINTENANCE: "Line-state / maintenance message",
            MessageCategory.ACK: "Acknowledgment",
            MessageCategory.CORRECTION: "Correction message",
            MessageCategory.WATCHTOWER_CRITICAL: "Watchtower critical sighting",
        }
        return labels.get(message.category, message.category.value)

    def _format_message_line(self, message: MissionMessage, status: Optional[str] = None) -> str:
        content = message.payload_text or "(no readable overlay; use technical bits and dashboard metrics)"
        status_text = f" | status={status}" if status else ""
        return (
            f"{message.message_id}: {self._message_label(message)} | "
            f"{message.source.value} -> {message.destination.value} | "
            f"priority={message.priority.value} | payload={message.payload_size_bits} bits | "
            f"deadline={message.deadline_cycle} | attempt={message.attempt}{status_text}\n"
            f"      mission_text=\"{content}\"\n"
            f"      technical_bits={self._short_bits(message.payload_bits)}"
        )

    def _message_status_for_cycle(self, message: MissionMessage, transmission_records: List[Dict[str, Any]],
                                  deferred_ids: List[str], receiver_records: List[Dict[str, Any]],
                                  cycle: int) -> str:
        parts = []
        parts.append("retransmitted" if message.attempt > 0 or message.created_at_cycle < cycle else "new")
        related = [r for r in transmission_records if r.get("message_id") == message.message_id]
        if message.message_id in set(deferred_ids):
            parts.append("deferred")
        if related:
            parts.append("transmitted")
            latest = related[-1]
            receiver_status = latest.get("receiver_status")
            if receiver_status == ReceiverStatus.ACCEPT.value:
                parts.append("accepted")
            elif receiver_status == ReceiverStatus.CORRECTED.value:
                parts.append("corrected")
            elif receiver_status in {ReceiverStatus.REJECT.value, ReceiverStatus.AMBIGUOUS.value, ReceiverStatus.INVALID_FRAME.value}:
                parts.append(receiver_status)
            elif receiver_status == ReceiverStatus.RETRANSMIT_REQUESTED.value:
                parts.append("retransmission-requested")
            if latest.get("retransmission_requested"):
                parts.append("retransmission-requested")
            if latest.get("accepted_incorrect"):
                parts.append("accepted-wrong")
        elif message.message_id not in set(deferred_ids):
            parts.append("queued/not-selected")
        # preserve order while removing duplicates
        out = []
        for p in parts:
            if p not in out:
                out.append(p)
        return ", ".join(out)

    def _delta(self, current: float | int, previous: float | int | None, *, precision: int = 3) -> str:
        if previous is None:
            return "new"
        diff = current - previous
        if isinstance(current, float) or isinstance(previous, float):
            return f"{diff:+.{precision}f}"
        return f"{int(diff):+d}"

    def _dict_delta_text(self, current: Dict[str, Any], previous: Dict[str, Any] | None, *, precision: int = 2) -> str:
        previous = previous or {}
        parts = []
        for key in sorted(set(current) | set(previous)):
            cur = current.get(key, 0)
            prev = previous.get(key, 0)
            try:
                diff = float(cur) - float(prev)
                diff_text = f"{diff:+.{precision}f}" if isinstance(cur, float) or isinstance(prev, float) else f"{int(diff):+d}"
            except Exception:
                diff_text = "n/a"
            parts.append(f"{key}={cur} ({diff_text})")
        return ", ".join(parts) if parts else "none"

    def _snapshot_compact_dict(self, snapshot: DashboardSnapshot) -> Dict[str, Any]:
        return {
            "capacity": snapshot.available_capacity_bits,
            "utilization": snapshot.link_utilization,
            "overhead": snapshot.overhead_ratio,
            "ber": snapshot.estimated_bit_error_rate,
            "burst": snapshot.burst_error_indicator,
            "detected": snapshot.detected_error_count,
            "undetected": snapshot.undetected_corruption_count,
            "accepted_wrong": snapshot.accepted_incorrect_count,
            "rejected": snapshot.rejected_frame_count,
            "corrected": snapshot.corrected_frame_count,
            "retransmissions": snapshot.retransmission_count,
        }

    def _read_cycle_command(self, prompt: str) -> str:
        if self.cycle_script:
            cmd = self.cycle_script.pop(0).strip()
            print(f"{prompt}{cmd}")
            return cmd
        if self.cycle_scripted_mode:
            cmd = "continue"
            print(f"{prompt}{cmd}")
            return cmd
        return input(prompt).strip()

    def _print_initial_educational_dashboard(self, cycles: int) -> None:
        if self.quiet or not self.cycle_dashboard:
            return
        link_state = self.scenario_engine.link_state_for(0, self.scenario_engine.active_event(0))
        self.metrics.capacity_available_bits = link_state.capacity_bits_per_cycle
        channel_profile = self.scenario_engine.channel_profile_for(0, self.scenario_engine.active_event(0))
        initial_state = self._build_system_state(0, self.scenario_engine.get_phase(0), self.scenario_engine.active_event(0), link_state, channel_profile)
        initial_snapshot = self.metrics.snapshot(self.scenario_id, 0, initial_state.phase, initial_state.active_event, self.queue, self.strategy, None)
        print("\n" + "=" * 96)
        print("OPERATION FOGLINE — EDUCATIONAL RUN DASHBOARD")
        print("=" * 96)
        print("Initial run setup")
        print(f"  Scenario      : {self.scenario_id.value}")
        print(f"  Strategy      : {self.strategy.name} — {self.strategy.description}")
        print(f"  Seed          : {self.seed}")
        print(f"  Planned cycles: {cycles}")
        print("\nAvailable resources at the beginning")
        print(f"  Link capacity : {link_state.capacity_bits_per_cycle} bits/cycle — maximum protected frame data allowed in one cycle.")
        print(f"  TDM slots     : {', '.join(link_state.available_slots)} — usable time slots this cycle.")
        print(f"  TDM slot size : {link_state.slot_capacity_bits} bits — nominal size used for slot reasoning and display.")
        print(f"  FDM bands     : {', '.join(link_state.available_bands)} — usable frequency/band partitions this cycle.")
        print(f"  FDM band size : {link_state.band_capacity_bits} bits — per-band capacity limit when FDM is active.")
        print(f"  Bad resources : bad_slot={link_state.bad_slot or 'none'}, bad_band={link_state.bad_band or 'none'} — these may suffer extra errors if used.")
        print("\nStarting dashboard values before Cycle 0")
        self._print_explained_dashboard(initial_snapshot, None)
        print("\nHow to read the cycle dashboard")
        print("  Each numeric value is shown with its change from the previous cycle in parentheses, for example (+0.125).")
        print("  After each cycle, generated messages, transmitted frames, receiver decisions, deferred messages, and dashboard changes are printed.")
        print("  Readable mission text is a narrative overlay beside payload_bits; it is not decoded from the bits and does not change transmission behavior.")
        print("  Some messages hint at future trouble, some are ordinary chatter, and some can be misleading; compare them with dashboard metrics.")
        print("  This mode pauses after every cycle. Press Enter to continue, or type 'freeze' to open the same strategy-edit dashboard used by real freezes.")
        print("=" * 96)

    def _print_explained_dashboard(self, snapshot: DashboardSnapshot, previous: DashboardSnapshot | None) -> None:
        prev = self._snapshot_compact_dict(previous) if previous else {}
        cur = self._snapshot_compact_dict(snapshot)
        print("\nDashboard after this point")
        print("-" * 96)
        print(f"Scenario/phase : {snapshot.scenario_id.value} / {snapshot.phase} | event={snapshot.active_event or 'none'}")
        print(f"Strategy       : {snapshot.current_strategy_name}")
        print(
            f"Capacity       : {cur['capacity']} bits/cycle ({self._delta(cur['capacity'], prev.get('capacity'))}) — link budget available this cycle."
        )
        print(
            f"Utilization    : {cur['utilization']:.3f} ({self._delta(cur['utilization'], prev.get('utilization'))}) — requested bits divided by capacity; >1.0 means overload/deferral pressure."
        )
        print(
            f"Overhead ratio : {cur['overhead']:.3f} ({self._delta(cur['overhead'], prev.get('overhead'))}) — redundancy bits divided by transmitted bits."
        )
        print(
            f"BER estimate   : {cur['ber']:.5f} ({self._delta(cur['ber'], prev.get('ber'), precision=5)}) — observed bit-error fraction from transmitted frames."
        )
        print(
            f"Burst index    : {cur['burst']:.3f} ({self._delta(cur['burst'], prev.get('burst'))}) — fraction of transmitted frames hit by burst-like corruption."
        )
        print(
            f"Detected errors: {cur['detected']} ({self._delta(cur['detected'], prev.get('detected'))}) | "
            f"undetected={cur['undetected']} ({self._delta(cur['undetected'], prev.get('undetected'))}) | "
            f"accepted_wrong={cur['accepted_wrong']} ({self._delta(cur['accepted_wrong'], prev.get('accepted_wrong'))}) — accepted_wrong is the serious unsafe case."
        )
        print(
            f"Receiver totals: rejected={cur['rejected']} ({self._delta(cur['rejected'], prev.get('rejected'))}) | "
            f"corrected={cur['corrected']} ({self._delta(cur['corrected'], prev.get('corrected'))}) | "
            f"retrans={cur['retransmissions']} ({self._delta(cur['retransmissions'], prev.get('retransmissions'))})"
        )
        print("Backlog/prio   : " + self._dict_delta_text(snapshot.backlog_by_priority, previous.backlog_by_priority if previous else None))
        print("Backlog/dept   : " + self._dict_delta_text(snapshot.backlog_by_department, previous.backlog_by_department if previous else None))
        print("Avg delay      : " + self._dict_delta_text(snapshot.average_delay_by_department, previous.average_delay_by_department if previous else None))
        if snapshot.freeze_reason:
            print(f"Freeze status  : REAL FREEZE — {snapshot.freeze_reason}")
        else:
            print("Freeze status  : no real freeze reached at this cycle.")
        print("-" * 96)

    def _print_cycle_educational_report(self, cycle: int, state: SystemState, new_messages: List[MissionMessage],
                                        active_messages: List[MissionMessage], protected_frames: List[ProtectedFrame],
                                        transmissions: List[TransmissionUnit], deferred_ids: List[str], mux_warnings: List[str],
                                        transmission_records: List[Dict[str, Any]], receiver_records: List[Dict[str, Any]],
                                        snapshot: DashboardSnapshot, previous_snapshot: DashboardSnapshot | None) -> None:
        if self.quiet or not self.cycle_dashboard:
            return
        print("\n" + "=" * 96)
        print(f"CYCLE {cycle:02d} — WHAT HAPPENED")
        print("=" * 96)
        print(f"Phase/event    : {state.phase} / {state.active_event or 'none'}")
        print(f"Channel profile: bit_error_rate={state.channel_profile.get('current_bit_error_rate', 0)} | "
              f"burst_probability={state.channel_profile.get('burst_probability', 0)} | "
              f"structured={state.channel_profile.get('structured_interference', False)}")
        print("\nMessages generated this cycle")
        if not new_messages:
            print("  none")
        for message in new_messages:
            status = self._message_status_for_cycle(message, transmission_records, deferred_ids, receiver_records, cycle)
            print("  - " + self._format_message_line(message, status))
        retrans_or_backlog = [m for m in active_messages if m.created_at_cycle < cycle or m.attempt > 0]
        if retrans_or_backlog:
            print("\nOlder queued/retransmission messages also considered")
            for message in retrans_or_backlog[:12]:
                status = self._message_status_for_cycle(message, transmission_records, deferred_ids, receiver_records, cycle)
                print("  - " + self._format_message_line(message, status))
            if len(retrans_or_backlog) > 12:
                print(f"  ... {len(retrans_or_backlog) - 12} more older queued messages")
        print("\nFrame preparation and scheduling")
        print(f"  Active messages considered: {len(active_messages)}")
        print(f"  Protected frames created  : {len(protected_frames)}")
        print(f"  Frames transmitted        : {len(transmissions)}")
        print(f"  Deferred message IDs      : {deferred_ids if deferred_ids else 'none'}")
        if mux_warnings:
            print(f"  Scheduling warnings       : {mux_warnings}")
        print("\nTransmitted frame details")
        if not transmission_records:
            print("  none — no frame fit the current capacity/quota/resource constraints.")
        for record in transmission_records:
            msg = self.message_by_id.get(record.get('message_id'))
            payload_bits = self._short_bits(msg.payload_bits) if msg else 'unknown'
            mission_text = (msg.payload_text if msg and msg.payload_text else record.get('payload_text') or '(no readable overlay)')
            print(
                "  - "
                f"{record.get('frame_id')} | msg={record.get('message_id')} | "
                f"{record.get('source')} -> {record.get('destination')} | "
                f"cat={record.get('category')} | prio={record.get('priority')} | "
                f"payload={record.get('payload_size_bits')} bits | "
                f"mission=\"{mission_text}\" | bits={payload_bits} | "
                f"method={record.get('error_control_method')} | mux={record.get('multiplexing_mode')} | "
                f"slot={record.get('assigned_slot') or '-'} band={record.get('assigned_band') or '-'} | "
                f"corrupted={record.get('was_corrupted')} ({record.get('corruption_type')}) | "
                f"receiver={record.get('receiver_status')} | accepted_wrong={record.get('accepted_incorrect')} | retrans_req={record.get('retransmission_requested')}"
            )
        print("\nReceiver decisions")
        if not receiver_records:
            print("  none")
        for decision in receiver_records:
            print(
                f"  - frame={decision.get('frame_id')} | status={decision.get('status')} | "
                f"confidence={decision.get('confidence')} | retransmit={decision.get('request_retransmission')} | reason={decision.get('reason')}"
            )
        self._print_explained_dashboard(snapshot, previous_snapshot)

    def _cycle_checkpoint(self, snapshot: DashboardSnapshot, state: SystemState) -> None:
        if self.quiet or not self.cycle_dashboard:
            return
        if snapshot.freeze_reason:
            if self.interactive_freeze:
                print("This cycle reached an automatic freeze. The configuration dashboard has already been shown; continue moves to the next cycle.")
            else:
                print("This cycle reached an automatic freeze threshold. It was logged for analysis; continue moves to the next cycle.")
        elif self.manual_freeze_enabled:
            print("This is a regular cycle checkpoint. Enter/continue moves to the next cycle; type 'freeze' only if you want to open the configuration editor now.")
        else:
            print("Manual checkpoint editing is disabled for this run. Enter/continue moves to the next cycle, or type quit.")

        prompt = "cycle checkpoint> " if self.manual_freeze_enabled else "continue/quit> "
        cmd = self._read_cycle_command(prompt).strip().lower()
        if cmd in {"", "continue", "c", "next", "n"}:
            return
        if cmd in {"quit", "exit", "q"}:
            raise KeyboardInterrupt("Run stopped from the cycle checkpoint.")
        if cmd in {"freeze", "manual_freeze", "checkpoint", "edit"}:
            if not self.manual_freeze_enabled:
                print("Manual checkpoint editing is disabled for this run; continuing to the next cycle.")
                return
            if self.interactive_dashboard is None:
                print("Manual checkpoint dashboard is unavailable; continuing.")
                return
            before_name = self.strategy.name
            manual_snapshot = copy.deepcopy(snapshot)
            manual_snapshot.freeze_reason = "manual_checkpoint"
            self.strategy = self.interactive_dashboard.edit(manual_snapshot, state, self.strategy)
            self.interactive_events.append({
                "cycle": snapshot.cycle,
                "freeze_reason": manual_snapshot.freeze_reason,
                "strategy_before": before_name,
                "strategy_after": self.strategy.name,
                "mode": "cycle_checkpoint",
            })
            print(f"Manual checkpoint complete: {before_name} -> {self.strategy.name}. Continuing run.")
            return
        allowed = "Enter/continue, freeze, or quit" if self.manual_freeze_enabled else "Enter/continue or quit"
        print(f"Unknown checkpoint command; continuing. Use {allowed}.")

    def _print_dashboard(self, snapshot: DashboardSnapshot) -> None:
        if self.quiet:
            return
        print(
            f"Cycle {snapshot.cycle:02d} | {snapshot.scenario_id.value} | {snapshot.phase} | "
            f"event={snapshot.active_event or 'none'} | strategy={snapshot.current_strategy_name}"
        )
        print(
            f"  capacity={snapshot.available_capacity_bits} bits/cycle (link limit) | "
            f"util={snapshot.link_utilization:.3f} (requested/capacity) | "
            f"overhead={snapshot.overhead_ratio:.3f} (redundancy share)"
        )
        print(
            f"  BER={snapshot.estimated_bit_error_rate:.5f} (observed bit-error rate) | "
            f"burst={snapshot.burst_error_indicator:.3f} (burst-hit fraction) | "
            f"accepted_wrong={snapshot.accepted_incorrect_count} (unsafe deliveries)"
        )
        print(
            f"  rejected={snapshot.rejected_frame_count} (safe drops) | "
            f"corrected={snapshot.corrected_frame_count} (repaired) | "
            f"retrans={snapshot.retransmission_count} (retry load)"
        )
        if snapshot.freeze_reason:
            print(f"  === FROZEN: {snapshot.freeze_reason} ===")

    def run(self) -> Dict[str, Any]:
        cycles = int(self.scenario_config.get("cycles", 40))
        if self.cycle_limit is not None:
            cycles = min(cycles, int(self.cycle_limit))
        self._print_initial_educational_dashboard(cycles)
        previous_snapshot: Optional[DashboardSnapshot] = None
        stopped_early = False
        for cycle in range(cycles):
            phase = self.scenario_engine.get_phase(cycle)
            active_event = self.scenario_engine.active_event(cycle)
            link_state = self.scenario_engine.link_state_for(cycle, active_event)
            channel_profile = self.scenario_engine.channel_profile_for(cycle, active_event)
            state = self._build_system_state(cycle, phase, active_event, link_state, channel_profile)
            self.metrics.capacity_available_bits = link_state.capacity_bits_per_cycle
            self.metrics.capacity_used_bits = 0
            self.metrics.capacity_requested_bits = 0
            expired = self.queue.expire_old(cycle)
            self.metrics.deadline_miss_count += expired
            new_messages = self.message_generator.generate(self.scenario_config, cycle, self.strategy, phase, active_event)
            self.metrics.generated_message_count += len(new_messages)
            for m in new_messages:
                self.message_by_id[m.message_id] = m
            self.queue.add_many(new_messages)
            if self.max_pending_messages is not None and len(self.queue.pending) > self.max_pending_messages:
                # Cap runaway queues so one pathological configuration cannot grow without bound
                # during short experimental runs.
                self.queue.pending.sort(key=lambda m: (PRIORITY_ORDER[m.priority], m.created_at_cycle, m.message_id))
                overflow = self.queue.pending[self.max_pending_messages:]
                self.queue.dropped.extend(overflow)
                self.metrics.deadline_miss_count += len(overflow)
                self.queue.pending = self.queue.pending[:self.max_pending_messages]
            active_messages = sorted(self.queue.view(), key=lambda m: (PRIORITY_ORDER[m.priority], m.created_at_cycle, m.message_id))
            protected_frames = self._prepare_frames(active_messages, state)
            queue_state = {
                "backlog_by_priority": self.queue.backlog_by_priority(),
                "backlog_by_department": self.queue.backlog_by_department(),
            }
            try:
                plan = self.loader.choose_multiplexing_plan(protected_frames, state, queue_state, self.strategy)
                transmissions, deferred_ids, used_bits, requested_bits, mux_warnings = self.validator.validate_and_schedule(plan, state)
            except Exception as exc:
                self.metrics.invalid_output_count += 1
                transmissions, deferred_ids, used_bits, requested_bits, mux_warnings = [], [pf.frame.message_id for pf in protected_frames], 0, sum(pf.total_size_bits for pf in protected_frames), [str(exc)]
            self.metrics.capacity_used_bits = used_bits
            self.metrics.capacity_requested_bits = requested_bits
            self.metrics.total_transmitted_bits += used_bits
            self.metrics.deferred_message_count += len(deferred_ids)
            if deferred_ids:
                self.metrics.deferred_cycle_count += 1
            delivered_ids: set[str] = set()
            processed_ids: set[str] = set()
            receiver_records = []
            channel_records = []
            transmission_records = []
            burst_count = 0
            bit_error_total = 0
            bit_total = 0
            detected_this_cycle = 0
            routine_watchtower_bits = 0
            for unit in transmissions:
                frame = unit.protected_frame.frame
                self.metrics.error_control_method_usage[unit.protected_frame.method.value] = self.metrics.error_control_method_usage.get(unit.protected_frame.method.value, 0) + 1
                self.metrics.multiplexing_mode_usage[unit.multiplexing_mode.value] = self.metrics.multiplexing_mode_usage.get(unit.multiplexing_mode.value, 0) + 1
                if unit.assigned_slot:
                    self.metrics.slot_usage[unit.assigned_slot] = self.metrics.slot_usage.get(unit.assigned_slot, 0) + 1
                if unit.assigned_band:
                    self.metrics.band_usage[unit.assigned_band] = self.metrics.band_usage.get(unit.assigned_band, 0) + 1
                processed_ids.add(frame.message_id)
                if frame.source == Department.WATCHTOWER and frame.category == MessageCategory.ROUTINE_REPORT:
                    routine_watchtower_bits += unit.protected_frame.total_size_bits
                received, hidden = self.channel.transmit(unit, state)
                bit_total += len(hidden.original_bits)
                diff = sum(1 for a, b in zip(hidden.original_bits, hidden.received_bits) if a != b)
                bit_error_total += diff
                if hidden.corruption_type == "burst":
                    burst_count += 1
                slot_key = unit.assigned_slot or "none"
                band_key = unit.assigned_band or "none"
                self.metrics.slot_attempts[slot_key] = self.metrics.slot_attempts.get(slot_key, 0) + 1
                self.metrics.band_attempts[band_key] = self.metrics.band_attempts.get(band_key, 0) + 1
                self.metrics.slot_errors[slot_key] = self.metrics.slot_errors.get(slot_key, 0) + (1 if hidden.was_corrupted else 0)
                self.metrics.band_errors[band_key] = self.metrics.band_errors.get(band_key, 0) + (1 if hidden.was_corrupted else 0)
                decision, was_delivered, accepted_wrong = self._process_receiver(received, hidden, state)
                if hidden.was_corrupted and decision and decision.status in (ReceiverStatus.REJECT, ReceiverStatus.RETRANSMIT_REQUESTED, ReceiverStatus.AMBIGUOUS, ReceiverStatus.INVALID_FRAME):
                    detected_this_cycle += 1
                if was_delivered:
                    delivered_ids.add(received.message_id)
                message_context = self.message_by_id.get(frame.message_id)
                transmission_records.append({
                    "message_id": frame.message_id,
                    "frame_id": frame.frame_id,
                    "created_at_cycle": message_context.created_at_cycle if message_context else None,
                    "deadline_cycle": message_context.deadline_cycle if message_context else None,
                    "source": frame.source.value,
                    "destination": frame.destination.value,
                    "category": frame.category.value,
                    "priority": frame.priority.value,
                    "payload_size_bits": frame.payload_length_bits,
                    "payload_bits": message_context.payload_bits if message_context else None,
                    "payload_text": message_context.payload_text if message_context else "",
                    "story_role": message_context.story_role if message_context else "",
                    "observability": message_context.observability if message_context else "",
                    "linked_scenario_event": message_context.linked_scenario_event if message_context else None,
                    "hint_strength": message_context.hint_strength if message_context else "",
                    "misleading": message_context.misleading if message_context else False,
                    "scenario_note": message_context.scenario_note if message_context else "",
                    "story_template_id": message_context.story_template_id if message_context else "",
                    "frame_size_bits": unit.protected_frame.total_size_bits,
                    "error_control_method": unit.protected_frame.method.value,
                    "multiplexing_mode": unit.multiplexing_mode.value,
                    "assigned_slot": unit.assigned_slot,
                    "assigned_band": unit.assigned_band,
                    "was_corrupted": hidden.was_corrupted,
                    "corruption_type": hidden.corruption_type,
                    "receiver_status": decision.status.value if decision else None,
                    "accepted_correct": bool(was_delivered and not accepted_wrong),
                    "accepted_incorrect": bool(accepted_wrong),
                    "retransmission_requested": bool(decision.request_retransmission) if decision else False,
                })
                channel_records.append(dataclass_to_json_dict(hidden))
                if decision:
                    receiver_records.append(dataclass_to_json_dict(decision))
            self.queue.remove_messages(processed_ids | delivered_ids)
            self.metrics.last_cycle_metrics = {
                "estimated_bit_error_rate": bit_error_total / max(1, bit_total),
                "burst_error_indicator": burst_count / max(1, len(transmissions)),
                "detected_frame_error_rate": detected_this_cycle / max(1, len(transmissions)),
                "routine_watchtower_capacity_share": routine_watchtower_bits / max(1, link_state.capacity_bits_per_cycle),
            }
            pre_snapshot = self.metrics.snapshot(self.scenario_id, cycle, phase, active_event, self.queue, self.strategy, None)
            freeze_reason = self.freeze_manager.check(self.scenario_id, self.metrics, pre_snapshot)
            if freeze_reason:
                pre_snapshot.freeze_reason = freeze_reason
                if self.interactive_dashboard is not None and self.interactive_freeze:
                    before_name = self.strategy.name
                    self.strategy = self.interactive_dashboard.edit(pre_snapshot, state, self.strategy)
                    self.interactive_events.append({
                        "cycle": cycle,
                        "freeze_reason": freeze_reason,
                        "strategy_before": before_name,
                        "strategy_after": self.strategy.name,
                        "mode": "interactive_freeze",
                    })
                elif self.strategy.auto_adapt:
                    before_name = self.strategy.name
                    self.strategy = self.loader.adapt_strategy(pre_snapshot, self.strategy, {"all_methods": [m.value for m in ErrorControlMethod]})
                    self.interactive_events.append({
                        "cycle": cycle,
                        "freeze_reason": freeze_reason,
                        "strategy_before": before_name,
                        "strategy_after": self.strategy.name,
                        "mode": "auto_adapt",
                    })
            snapshot = self.metrics.snapshot(self.scenario_id, cycle, phase, active_event, self.queue, self.strategy, freeze_reason)
            if self.cycle_dashboard and not self.quiet:
                self._print_cycle_educational_report(cycle, state, new_messages, active_messages, protected_frames, transmissions, deferred_ids, mux_warnings, transmission_records, receiver_records, snapshot, previous_snapshot)
            else:
                self._print_dashboard(snapshot)
            if self.logger is not None:
                self.logger.log_cycle({
                    "cycle": cycle,
                    "phase": phase,
                    "active_event": active_event,
                    "strategy_name": self.strategy.name,
                    "messages_generated": [dataclass_to_json_dict(m) for m in new_messages],
                    "frames_requested": len(protected_frames),
                    "frames_transmitted": len(transmissions),
                    "frames_transmitted_details": transmission_records,
                    "deferred_message_ids": deferred_ids,
                    "multiplexing_warnings": mux_warnings,
                    "channel_records": channel_records,
                    "receiver_decisions": receiver_records,
                    "metrics": {
                        "capacity_requested_bits": requested_bits,
                        "capacity_used_bits": used_bits,
                        "capacity_available_bits": link_state.capacity_bits_per_cycle,
                        "link_utilization": snapshot.link_utilization,
                        "accepted_incorrect_count": self.metrics.accepted_incorrect_count,
                        "rejected_frame_count": self.metrics.rejected_frame_count,
                        "corrected_frame_count": self.metrics.corrected_frame_count,
                        "retransmission_count": self.metrics.retransmission_count,
                        "deadline_miss_count": self.metrics.deadline_miss_count,
                        "estimated_bit_error_rate": snapshot.estimated_bit_error_rate,
                        "burst_error_indicator": snapshot.burst_error_indicator,
                        "detected_frame_error_rate": self.metrics.last_cycle_metrics.get("detected_frame_error_rate", 0.0),
                        "routine_watchtower_capacity_share": self.metrics.last_cycle_metrics.get("routine_watchtower_capacity_share", 0.0),
                    },
                    "freeze_reason": freeze_reason,
                    "interactive_events": list(self.interactive_events),
                })
            self.metrics.cycles_survived += 1
            try:
                self._cycle_checkpoint(snapshot, state)
            except KeyboardInterrupt as exc:
                if not self.quiet:
                    print(str(exc))
                stopped_early = True
                previous_snapshot = snapshot
                break
            previous_snapshot = snapshot
        final_cycle = self.metrics.cycles_survived if stopped_early else cycles
        final_metrics = dataclass_to_json_dict(self.metrics.snapshot(self.scenario_id, final_cycle, "complete", None, self.queue, self.strategy, None))
        grading_summary = self.grading.grade(self.scenario_id, self.metrics, cycles)
        if self.logger is not None:
            json_path, csv_path = self.logger.save(final_metrics, grading_summary)
        else:
            json_path, csv_path = None, None
        return {
            "scenario_id": self.scenario_id.value,
            "strategy_name": self.strategy_name,
            "final_strategy_name": self.strategy.name,
            "seed": self.seed,
            "json_log": str(json_path) if json_path else None,
            "csv_log": str(csv_path) if csv_path else None,
            "grading_summary": grading_summary,
            "interactive_events": list(self.interactive_events),
            "stopped_early": stopped_early,
            "final_metrics": {
                "generated": self.metrics.generated_message_count,
                "delivered": self.metrics.delivered_message_count,
                "correct": self.metrics.correct_delivery_count,
                "accepted_wrong": self.metrics.accepted_incorrect_count,
                "accepted_wrong_critical": self.metrics.accepted_incorrect_critical,
                "deadline_misses": self.metrics.deadline_miss_count,
                "retransmissions": self.metrics.retransmission_count,
                "freezes": self.metrics.freeze_count,
                "capacity_requested_bits": self.metrics.capacity_requested_bits,
                "capacity_used_bits": self.metrics.capacity_used_bits,
                "deferred_messages": self.metrics.deferred_message_count,
                "deferred_cycles": self.metrics.deferred_cycle_count,
                "method_usage": {k: v for k, v in self.metrics.error_control_method_usage.items() if v},
                "mux_usage": {k: v for k, v in self.metrics.multiplexing_mode_usage.items() if v},
                "slot_usage": dict(sorted(self.metrics.slot_usage.items())),
                "band_usage": dict(sorted(self.metrics.band_usage.items())),
            },
        }


# ---------------------------------------------------------------------------
# Public run helpers
# ---------------------------------------------------------------------------

def run_single(project_root: Path, scenario: str, strategy: str, seed: int = 42, quiet: bool = False,
               auto_adapt: bool = False, interactive_freeze: bool = False,
               interactive_script: Optional[List[str]] = None, save_logs: bool = True,
               cycle_dashboard: bool = False, cycle_script: Optional[List[str]] = None,
               cycle_limit: Optional[int] = None, manual_freeze_enabled: bool = True) -> Dict[str, Any]:
    runtime = SimulationRuntime(
        project_root, ScenarioId(scenario), strategy, seed=seed, quiet=quiet,
        auto_adapt=auto_adapt, interactive_freeze=interactive_freeze,
        interactive_script=interactive_script, save_logs=save_logs,
        cycle_dashboard=cycle_dashboard, cycle_script=cycle_script, cycle_limit=cycle_limit,
        manual_freeze_enabled=manual_freeze_enabled,
    )
    return runtime.run()


def run_strategy_config(project_root: Path, scenario: str, strategy_config: StrategyConfig, seed: int = 42, quiet: bool = True,
                        save_logs: bool = False, cycle_limit: Optional[int] = None,
                        max_pending_messages: Optional[int] = None) -> Dict[str, Any]:
    runtime = SimulationRuntime(
        project_root, ScenarioId(scenario), strategy_config.name, seed=seed, quiet=quiet,
        strategy_override=strategy_config, save_logs=save_logs,
        cycle_limit=cycle_limit, max_pending_messages=max_pending_messages,
    )
    return runtime.run()



