"""
Operation Fogline story/message catalog.

This module is intentionally independent from the simulator's bit-level random
number generator. Readable mission text is a narrative overlay; payload_bits
remain the true technical payload and are not encoded from this text.
"""
from __future__ import annotations

import copy
import zlib
from typing import Any, Dict, List, Optional

DEFAULT_STORY_METADATA = {
    "payload_text": "",
    "story_role": "ordinary_chatter",
    "observability": "none",
    "linked_scenario_event": None,
    "hint_strength": "none",
    "misleading": False,
    "scenario_note": "",
}

# Role selection keeps the environment partly observable:
# ordinary ≈ 55-70%, context/retrospective ≈ 10-20%, hints ≈ 10-15%, false ≈ 5-10%, plus some no-story messages.
ROLE_BUCKETS = [
    (0.08, "false_alarm"),
    (0.28, "preemptive_hint"),
    (0.43, "contextual"),
    (0.90, "ordinary_chatter"),
    (1.00, "no_story"),
]

CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "scenario_1_first_fog": [
        {
            "id": "s1_ordinary_001", "cycle_window": [0, 8], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "low",
            "payload_text": "Visibility along the lower pier is falling. Lantern markers remain visible at close range only.",
            "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s1_ordinary_002", "cycle_window": [0, 10], "source": "radar", "destination": "command", "category": "detection_alert", "priority": "medium",
            "payload_text": "Small echo cluster faded behind the fog bank. No confirmed hostile pattern.",
            "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s1_ordinary_003", "cycle_window": [0, 12], "source": "command", "destination": "radar", "category": "control_message", "priority": "medium",
            "payload_text": "Continue short-interval sweeps. Report only confirmed movement until further notice.",
            "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s1_context_001", "cycle_window": [3, 14], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "low",
            "payload_text": "Patrol reports wet cable housings near the old service stair. No break observed.",
            "story_role": "context", "observability": "medium", "hint_strength": "weak", "linked_scenario_event": "rising_random_noise", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s1_hint_001", "cycle_window": [6, 18], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "medium",
            "payload_text": "Glass insulators on the south line are sweating heavily. Occasional blue sparks seen near the junction box.",
            "story_role": "preemptive_hint", "observability": "medium", "hint_strength": "moderate", "linked_scenario_event": "rising_random_noise", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s1_hint_002", "cycle_window": [8, 20], "source": "command", "destination": "radar", "category": "control_message", "priority": "high",
            "payload_text": "If the fog thickens further, shorten nonessential reports and preserve alert traffic.",
            "story_role": "preemptive_hint", "observability": "medium", "hint_strength": "moderate", "linked_scenario_event": "priority_pressure_under_noise", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s1_context_002", "cycle_window": [10, 24], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "low",
            "payload_text": "The harbor bell sounds muffled from half its usual distance. Moisture is collecting on exposed fittings.",
            "story_role": "context", "observability": "low", "hint_strength": "weak", "linked_scenario_event": "weather_degradation", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s1_false_001", "cycle_window": [8, 22], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "low",
            "payload_text": "Report of line noise traced to a loose lantern chain, not the cable.",
            "story_role": "false_alarm", "observability": "medium", "hint_strength": "weak", "linked_scenario_event": None, "misleading": True,
            "scenario_note": "",
        },
        {
            "id": "s1_retrospective_001", "cycle_window": [15, 30], "source": "command", "destination": "watchtower", "category": "control_message", "priority": "medium",
            "payload_text": "Several recent reports arrived late or incomplete. Keep routine observations brief until the line steadies.",
            "story_role": "retrospective_explanation", "observability": "high", "hint_strength": "moderate", "linked_scenario_event": "observed_delay_or_rejections", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s1_ordinary_004", "cycle_window": [12, 32], "source": "radar", "destination": "command", "category": "detection_alert", "priority": "high",
            "payload_text": "Sweep interval complete. Contact strength uneven, likely weather scatter rather than aircraft.",
            "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s1_ordinary_005", "cycle_window": [18, 36], "source": "command", "destination": "watchtower", "category": "control_message", "priority": "medium",
            "payload_text": "Maintain pier watch and report only changes that affect line crews or shore movement.",
            "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
            "scenario_note": "",
        },
    ],
    "scenario_2_enemy_learns": [
        {
            "id": "s2_ordinary_001", "cycle_window": [0, 8], "source": "radar", "destination": "command", "category": "detection_alert", "priority": "high",
            "payload_text": "Coastal sweep complete. Two weak contacts lost behind headland clutter.",
            "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s2_ordinary_002", "cycle_window": [0, 12], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "low",
            "payload_text": "Fishing lamps observed beyond the outer rocks. Pattern irregular but not confirmed hostile.",
            "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s2_ordinary_003", "cycle_window": [0, 14], "source": "command", "destination": "watchtower", "category": "control_message", "priority": "medium",
            "payload_text": "Do not interrupt Radar alert traffic unless visual confirmation improves.",
            "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s2_hint_001", "cycle_window": [6, 18], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "medium",
            "payload_text": "The same lamp pattern repeated three times at equal intervals. It does not match civilian signaling.",
            "story_role": "preemptive_hint", "observability": "medium", "hint_strength": "moderate", "linked_scenario_event": "structured_interference_possible", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s2_hint_002", "cycle_window": [8, 22], "source": "radar", "destination": "command", "category": "detection_alert", "priority": "high",
            "payload_text": "Two reports returned with matching control marks but conflicting bearing values.",
            "story_role": "preemptive_hint", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "weak_validation_may_fail", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s2_hint_003", "cycle_window": [10, 24], "source": "command", "destination": "radar", "category": "control_message", "priority": "high",
            "payload_text": "If repeated control marks appear again, treat ambiguous reports as unsafe rather than merely delayed.",
            "story_role": "preemptive_hint", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "receiver_strictness_needed", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s2_context_001", "cycle_window": [12, 28], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "medium",
            "payload_text": "Operators report a harsh clicking tone on the line during the last burst of interference.",
            "story_role": "retrospective_explanation", "observability": "high", "hint_strength": "moderate", "linked_scenario_event": "burst_errors_active", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s2_context_002", "cycle_window": [14, 30], "source": "radar", "destination": "command", "category": "detection_alert", "priority": "high",
            "payload_text": "Bearing reports are arriving in pairs: one plausible, one shifted by a fixed amount.",
            "story_role": "context", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "structured_multi_bit_changes", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s2_false_001", "cycle_window": [10, 26], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "low",
            "payload_text": "The lamp pattern stopped after the fog shifted. It may have been surf reflection.",
            "story_role": "false_alarm", "observability": "medium", "hint_strength": "weak", "linked_scenario_event": None, "misleading": True,
            "scenario_note": "",
        },
        {
            "id": "s2_false_002", "cycle_window": [16, 32], "source": "command", "destination": "watchtower", "category": "control_message", "priority": "medium",
            "payload_text": "Line crew found no physical cut near the watch post. Continue normal visual reporting.",
            "story_role": "false_alarm", "observability": "medium", "hint_strength": "weak", "linked_scenario_event": None, "misleading": True,
            "scenario_note": "",
        },
        {
            "id": "s2_retrospective_001", "cycle_window": [22, 38], "source": "command", "destination": "radar", "category": "control_message", "priority": "high",
            "payload_text": "A previously accepted bearing report no longer matches the plotted track. Mark similar frames suspicious.",
            "story_role": "retrospective_explanation", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "accepted_wrong_detected_late", "misleading": False,
            "scenario_note": "",
        },
    ],
    "scenario_3_blackout_hour": [
        {
            "id": "s3_ordinary_001", "cycle_window": [0, 8], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "low",
            "payload_text": "Harbor road remains passable. Civilians moving inland under escort.",
            "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s3_ordinary_002", "cycle_window": [0, 10], "source": "radar", "destination": "command", "category": "detection_alert", "priority": "high",
            "payload_text": "Intermittent contacts beyond the southern fog wall. Altitude estimate uncertain.",
            "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s3_ordinary_003", "cycle_window": [0, 12], "source": "command", "destination": "watchtower", "category": "control_message", "priority": "medium",
            "payload_text": "Hold routine patrol details unless they affect shore defenses.",
            "story_role": "ordinary_chatter", "observability": "medium", "hint_strength": "weak", "linked_scenario_event": "priority_pressure", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s3_hint_001", "cycle_window": [6, 16], "source": "radar", "destination": "command", "category": "detection_alert", "priority": "critical",
            "payload_text": "Bomber formation descending below cloud cover. Bearing suggests approach toward the west relay trench.",
            "story_role": "preemptive_hint", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "possible_capacity_reduction", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s3_hint_002", "cycle_window": [8, 18], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "medium",
            "payload_text": "Relay crew reports vibration in the west trench after distant impacts. Line still carries signal, but casing is exposed.",
            "story_role": "preemptive_hint", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "relay_damage_risk", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s3_hint_003", "cycle_window": [10, 20], "source": "command", "destination": "radar", "category": "control_message", "priority": "critical",
            "payload_text": "If the relay trench is struck, emergency orders must outrank routine Watchtower traffic.",
            "story_role": "preemptive_hint", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "emergency_priority_needed", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s3_context_001", "cycle_window": [12, 24], "source": "watchtower", "destination": "command", "category": "watchtower_critical", "priority": "high",
            "payload_text": "West relay trench hit. Crew reports one line dark and one line unstable.",
            "story_role": "retrospective_explanation", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "capacity_reduction_active", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s3_false_001", "cycle_window": [8, 22], "source": "radar", "destination": "command", "category": "detection_alert", "priority": "high",
            "payload_text": "Bomber group released early. Impacts fell short of the relay trench. Line crews report no direct hit.",
            "story_role": "false_alarm", "observability": "high", "hint_strength": "moderate", "linked_scenario_event": "missed_attack", "misleading": True,
            "scenario_note": "",
        },
        {
            "id": "s3_context_002", "cycle_window": [14, 28], "source": "command", "destination": "watchtower", "category": "control_message", "priority": "high",
            "payload_text": "Send only line-state, casualty, or shore-defense reports until emergency traffic clears.",
            "story_role": "context", "observability": "high", "hint_strength": "moderate", "linked_scenario_event": "low_priority_suppression_needed", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s3_hint_004", "cycle_window": [16, 30], "source": "radar", "destination": "command", "category": "detection_alert", "priority": "critical",
            "payload_text": "Multiple low contacts turning inland. Window for relay orders may be shorter than expected.",
            "story_role": "preemptive_hint", "observability": "medium", "hint_strength": "strong", "linked_scenario_event": "emergency_deadline_pressure", "misleading": False,
            "scenario_note": "",
        },
        {
            "id": "s3_retrospective_001", "cycle_window": [20, 36], "source": "command", "destination": "radar", "category": "emergency_code", "priority": "critical",
            "payload_text": "Emergency code traffic is backing up behind routine reports. Short commands must clear first.",
            "story_role": "retrospective_explanation", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "deadline_misses_or_backlog", "misleading": False,
            "scenario_note": "",
        },
    ],
}


# Second-pass integration additions: exact source/destination/category templates for generated
# message combinations that previously needed neutral fallbacks.  These keep the readable layer
# operationally consistent without changing payload bits or simulator scoring.
CATALOG["scenario_1_first_fog"].extend([
    {
        "id": "s1_hint_003", "cycle_window": [6, 20], "source": "radar", "destination": "command", "category": "detection_alert", "priority": "high",
        "payload_text": "Radar returns are flickering at the fog edge; the same sweep is clear one pass and broken the next.",
        "story_role": "preemptive_hint", "observability": "medium", "hint_strength": "moderate", "linked_scenario_event": "rising_random_noise", "misleading": False,
        "scenario_note": "",
    },
    {
        "id": "s1_context_003", "cycle_window": [4, 24], "source": "command", "destination": "radar", "category": "control_message", "priority": "high",
        "payload_text": "Command notes several fog-muted reports and asks Radar to keep alert summaries concise until the line steadies.",
        "story_role": "context", "observability": "medium", "hint_strength": "weak", "linked_scenario_event": "weather_degradation", "misleading": False,
        "scenario_note": "",
    },
])

CATALOG["scenario_2_enemy_learns"].extend([
    {
        "id": "s2_ordinary_004", "cycle_window": [0, 18], "source": "command", "destination": "radar", "category": "control_message", "priority": "critical",
        "payload_text": "Command asks Radar to preserve original bearing notes before summarizing the next sweep.",
        "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
        "scenario_note": "",
    },
    {
        "id": "s2_false_003", "cycle_window": [12, 30], "source": "command", "destination": "radar", "category": "control_message", "priority": "critical",
        "payload_text": "Command reports the repeated control mark may be an operator shorthand from the previous watch.",
        "story_role": "false_alarm", "observability": "medium", "hint_strength": "weak", "linked_scenario_event": None, "misleading": True,
        "scenario_note": "",
    },
])

CATALOG["scenario_3_blackout_hour"].extend([
    {
        "id": "s3_ordinary_004", "cycle_window": [0, 14], "source": "command", "destination": "radar", "category": "emergency_code", "priority": "critical",
        "payload_text": "Command sends a short emergency code to Radar confirming the blackout watch schedule.",
        "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
        "scenario_note": "",
    },
    {
        "id": "s3_hint_005", "cycle_window": [8, 24], "source": "command", "destination": "radar", "category": "emergency_code", "priority": "critical",
        "payload_text": "Command compresses relay instructions into the shortest emergency code the operators can safely recognize.",
        "story_role": "preemptive_hint", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "emergency_deadline_pressure", "misleading": False,
        "scenario_note": "",
    },
    {
        "id": "s3_hint_006", "cycle_window": [9, 24], "source": "command", "destination": "watchtower", "category": "control_message", "priority": "critical",
        "payload_text": "Command orders Watchtower to hold decorative patrol detail and send only line-state or shore-defense changes.",
        "story_role": "preemptive_hint", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "low_priority_suppression_needed", "misleading": False,
        "scenario_note": "",
    },
    {
        "id": "s3_ordinary_005", "cycle_window": [0, 18], "source": "watchtower", "destination": "command", "category": "watchtower_critical", "priority": "high",
        "payload_text": "Watchtower reports a brief silhouette above the south wall, then loses it behind smoke and fog.",
        "story_role": "ordinary_chatter", "observability": "low", "hint_strength": "none", "linked_scenario_event": None, "misleading": False,
        "scenario_note": "",
    },
    {
        "id": "s3_hint_007", "cycle_window": [10, 26], "source": "watchtower", "destination": "command", "category": "watchtower_critical", "priority": "high",
        "payload_text": "Watchtower sees dust from the relay trench before the sound reaches the pier; the line crew has not answered twice.",
        "story_role": "preemptive_hint", "observability": "high", "hint_strength": "strong", "linked_scenario_event": "relay_damage_risk", "misleading": False,
        "scenario_note": "",
    },
    {
        "id": "s3_hint_008", "cycle_window": [8, 24], "source": "watchtower", "destination": "command", "category": "routine_report", "priority": "low",
        "payload_text": "Routine patrol detail is piling up at the desk while relay crews ask whether only emergency line reports should pass.",
        "story_role": "preemptive_hint", "observability": "medium", "hint_strength": "moderate", "linked_scenario_event": "routine_traffic_pressure", "misleading": False,
        "scenario_note": "",
    },
])

HIDDEN_BACKGROUND_REFERENCES = {
    "scenario_1_first_fog": {
        "story_role": "hidden_background_reference", "observability": "none", "linked_scenario_event": "unmessaged_random_ber_shift", "hint_strength": "none", "misleading": False,
        "scenario_note": "",
    },
    "scenario_2_enemy_learns": {
        "story_role": "hidden_background_reference", "observability": "none", "linked_scenario_event": "unmessaged_structured_corruption", "hint_strength": "none", "misleading": False,
        "scenario_note": "",
    },
    "scenario_3_blackout_hour": {
        "story_role": "hidden_background_reference", "observability": "none", "linked_scenario_event": "unmessaged_capacity_loss_or_traffic_surge", "hint_strength": "none", "misleading": False,
        "scenario_note": "",
    },
}


def stable_float(*parts: Any) -> float:
    text = "|".join(str(p) for p in parts)
    return (zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF) / 0x100000000


def stable_index(length: int, *parts: Any) -> int:
    if length <= 0:
        return 0
    text = "|".join(str(p) for p in parts)
    return (zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF) % length


def role_for_message(scenario_id: str, cycle: int, source: str, destination: str, category: str, priority: str, counter: int, phase: Optional[str], active_event: Optional[str]) -> str:
    r = stable_float("story_role", scenario_id, cycle, source, destination, category, priority, counter, phase or "", active_event or "")
    for upper, role in ROLE_BUCKETS:
        if r < upper:
            return role
    return "ordinary_chatter"


def in_window(item: Dict[str, Any], cycle: int) -> bool:
    window = item.get("cycle_window", [0, 10**9])
    if window == "any":
        return True
    if isinstance(window, list) and len(window) == 2:
        return int(window[0]) <= cycle <= int(window[1])
    return True


def role_matches(item_role: str, requested_role: str) -> bool:
    if requested_role == "contextual":
        return item_role in {"context", "retrospective_explanation"}
    return item_role == requested_role


def score_template(item: Dict[str, Any], source: str, destination: str, category: str, priority: str) -> int:
    score = 0
    if item.get("source") == source:
        score += 4
    if item.get("destination") == destination:
        score += 3
    if item.get("category") == category:
        score += 4
    if item.get("priority") == priority:
        score += 1
    return score


def exact_operational_match(item: Dict[str, Any], source: str, destination: str, category: str) -> bool:
    """A student-facing story template must not change who is speaking or what kind of message it is.

    Earlier versions used weighted similarity, which preserved scenario theme but could attach, for
    example, a Watchtower cable report to a Radar detection frame.  That made the readable layer
    pedagogically confusing even though the technical bits were unaffected.  The selector now only
    uses catalog templates whose source, destination, and category exactly match the generated
    MissionMessage.  If no exact template exists, it creates a neutral source/category-consistent
    fallback instead of borrowing an incompatible message.
    """
    return item.get("source") == source and item.get("destination") == destination and item.get("category") == category


def fallback_story_for_message(
    scenario_id: str,
    cycle: int,
    source: str,
    destination: str,
    category: str,
    priority: str,
    requested_role: str,
) -> Dict[str, Any]:
    """Create a neutral, source-consistent story when the catalog lacks an exact template.

    The fallback remains a narrative overlay only. It is intentionally ordinary/contextual and
    does not leak hidden scenario state or prescribe a strategy.
    """
    source_name = {"radar": "Radar", "watchtower": "Watchtower", "command": "Command"}.get(source, source.title())
    dest_name = {"radar": "Radar", "watchtower": "Watchtower", "command": "Command"}.get(destination, destination.title())

    scenario_texture = {
        "scenario_1_first_fog": "through the damp fog line",
        "scenario_2_enemy_learns": "while operators compare repeated signal patterns",
        "scenario_3_blackout_hour": "under blackout traffic discipline",
    }.get(scenario_id, "during the current watch")

    category_text = {
        "detection_alert": f"{source_name} sends a contact update to {dest_name} {scenario_texture}. The bearing remains uncertain and must be checked against later reports.",
        "routine_report": f"{source_name} sends a routine line-and-visibility report to {dest_name} {scenario_texture}. No single observation should be treated as decisive.",
        "control_message": f"{source_name} sends a control instruction to {dest_name} {scenario_texture}. Operators are reminded to compare orders with the live dashboard load.",
        "emergency_code": f"{source_name} sends a compact emergency code to {dest_name} {scenario_texture}. The message is short, urgent, and still carried as technical bits.",
        "watchtower_critical": f"{source_name} sends a critical visual sighting to {dest_name} {scenario_texture}. The report may affect priority decisions but does not name a strategy.",
        "maintenance": f"{source_name} sends a line-state maintenance note to {dest_name} {scenario_texture}. The crew report is observational rather than conclusive.",
        "ack": f"{source_name} acknowledges {dest_name}'s last confirmed instruction {scenario_texture}.",
        "correction": f"{source_name} sends a correction notice to {dest_name} {scenario_texture}. Operators should verify it against confirmed traffic.",
    }.get(category, f"{source_name} sends an operational message to {dest_name} {scenario_texture}.")

    role = "ordinary_chatter"
    observability = "low"
    hint_strength = "none"
    misleading = False
    if requested_role in {"contextual", "context", "retrospective_explanation"}:
        role = "context"
        observability = "medium"
        hint_strength = "weak"
    elif requested_role == "false_alarm":
        role = "false_alarm"
        observability = "medium"
        hint_strength = "weak"
        misleading = True
        category_text += " The observation may turn out to be unrelated to the channel behavior."
    elif requested_role == "preemptive_hint":
        # Avoid inventing strong hints for unsupported source/category combinations.
        role = "context"
        observability = "medium"
        hint_strength = "weak"

    return {
        "payload_text": category_text,
        "story_role": role,
        "observability": observability,
        "linked_scenario_event": None,
        "hint_strength": hint_strength,
        "misleading": misleading,
        "scenario_note": "",
        "story_template_id": f"fallback_{scenario_id}_{source}_{destination}_{category}_{role}",
    }


def copy_story_fields(chosen: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(DEFAULT_STORY_METADATA)
    for key in out:
        if key in chosen:
            out[key] = chosen[key]
    out["story_template_id"] = chosen.get("story_template_id") or chosen.get("id", "")
    return out


def select_story_for_message(
    scenario_id: str,
    cycle: int,
    source: str,
    destination: str,
    category: str,
    priority: str,
    counter: int,
    phase: Optional[str] = None,
    active_event: Optional[str] = None,
) -> Dict[str, Any]:
    """Return narrative metadata for a mission message.

    The returned text is not derived from payload bits. This function uses a
    deterministic CRC32-based selector so it never consumes the simulator's RNG
    and therefore cannot perturb bit payloads, channel corruption, scoring, or
    baseline behavior.

    Student-facing templates must be source/destination/category consistent. If
    the requested role has no exact template for the generated MissionMessage,
    the selector either falls back to another exact template for that same
    source/destination/category or creates a neutral consistent fallback.
    """
    role = role_for_message(scenario_id, cycle, source, destination, category, priority, counter, phase, active_event)
    if role == "no_story":
        meta = copy.deepcopy(DEFAULT_STORY_METADATA)
        meta["story_role"] = "ordinary_chatter"
        meta["observability"] = "none"
        meta["scenario_note"] = "No readable overlay selected for this message; the analysis should rely on metrics or other messages."
        return meta

    catalog_items = [item for item in CATALOG.get(scenario_id, []) if in_window(item, cycle)]
    exact_items = [item for item in catalog_items if exact_operational_match(item, source, destination, category)]

    candidates = [item for item in exact_items if role_matches(str(item.get("story_role", "ordinary_chatter")), role)]

    if not candidates and role == "preemptive_hint":
        # Do not invent strong hints at the wrong source/category. Use ordinary exact chatter if available.
        candidates = [item for item in exact_items if item.get("story_role") == "ordinary_chatter"]

    if candidates:
        # Prefer exact priority when available, but never sacrifice source/destination/category consistency.
        scored = [(1 if item.get("priority") == priority else 0, item) for item in candidates]
        best_score = max(score for score, _ in scored)
        best = [item for score, item in scored if score == best_score]
        chosen = copy.deepcopy(best[stable_index(len(best), "story_choice", scenario_id, cycle, source, destination, category, priority, counter, phase or "", active_event or "")])
        return copy_story_fields(chosen)

    # No exact template exists for the requested role. Create a neutral source/destination/category-
    # consistent fallback rather than borrowing an incompatible or over-informative template.
    return fallback_story_for_message(scenario_id, cycle, source, destination, category, priority, role)
