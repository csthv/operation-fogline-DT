"""Operation Fogline runner and console dashboard.

This module contains two public entry points: a command-line runner and an
interactive dashboard. The simulator engine itself lives in ``simulator_core``;
this file is intentionally focused on user-facing configuration, preset
building, and readable run output.
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from simulator_core import (
    ScenarioId,
    run_single,
    StudentModuleLoader,
    ErrorControlMethod,
    MultiplexingMode,
    Priority,
    MessageCategory,
)
from student_modules import list_strategies, all_strategy_names, save_custom_strategy


def _script_or_input(commands: list[str] | None, prompt: str, *, default_when_empty: str | None = None) -> str:
    if commands is not None:
        if commands:
            cmd = commands.pop(0).strip()
            print(f"{prompt}{cmd}")
            return cmd
        if default_when_empty is not None:
            print(f"{prompt}{default_when_empty}")
            return default_when_empty
    return input(prompt).strip()


def _bool_from_token(token: str) -> bool:
    return token.strip().lower() in {"1", "true", "yes", "y", "on", "enable", "enabled"}


def _normalize_alloc_dict(alloc: dict[str, float] | None) -> dict[str, float]:
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


def _print_run_result(result: dict) -> None:
    print("\nRun complete")
    print("=" * 60)
    print(f"Scenario: {result['scenario_id']}")
    print(f"Initial strategy: {result['strategy_name']}")
    print(f"Final strategy: {result.get('final_strategy_name', result['strategy_name'])}")
    print(f"Score: {result['grading_summary']['score']}")
    print(f"JSON log: {result['json_log']}")
    print(f"CSV log:  {result['csv_log']}")
    if result.get("interactive_events"):
        print("Strategy/configuration changes:")
        for event in result["interactive_events"]:
            print(f"  cycle {event['cycle']}: {event['strategy_before']} -> {event['strategy_after']} ({event['mode']}, reason={event['freeze_reason']})")
    print("Final metrics:")
    for k, v in result["final_metrics"].items():
        print(f"  {k}: {v}")


def _print_strategy_groups() -> None:
    groups = list_strategies()
    for scenario, strategies in groups.items():
        print(f"\n{scenario}")
        for strategy in strategies:
            print(f"  - {strategy}")



def _strategy_summary_lines(current) -> list[str]:
    return [
        f"Name: {current.name}",
        f"Description: {current.description}",
        f"Multiplexing: {current.multiplexing_mode.value}",
        f"Receiver strictness: {current.receiver_strictness}",
        f"Compact emergency mode: {current.use_compact_emergency_mode}",
        f"Suppress routine Watchtower: {current.suppress_routine_watchtower}",
        f"Watchtower report limit: {current.watchtower_reports_per_cycle_limit}",
        "Error control by priority: " + str({k: v.value for k, v in current.error_control_by_priority.items()}),
        "Error control by category: " + str({k: v.value for k, v in current.error_control_by_category.items()}),
        f"Retransmission limits: {current.retransmission_limits_by_priority}",
        f"TDM allocation: {current.tdm_allocation}",
        f"FDM allocation: {current.fdm_allocation}",
        f"Avoid slots: {current.avoid_slots}",
        f"Avoid bands: {current.avoid_bands}",
        f"Force equal FDM: {current.force_equal_fdm}",
        f"Notes: {current.notes}",
    ]


def _print_strategy_summary(current) -> None:
    print("\nCurrent preset configuration")
    print("-" * 60)
    for line in _strategy_summary_lines(current):
        print("  " + line)


def _print_capabilities() -> None:
    print("\nExposed module/configuration capabilities")
    print("-" * 60)
    print("  Error-control methods:")
    for method in ErrorControlMethod:
        print(f"    - {method.value}")
    print("  Multiplexing modes: tdm, fdm")
    print("  Receiver strictness modes: normal, strict, very_strict")
    print("  Priorities: low, medium, high, critical")
    print("  Message categories:")
    for category in MessageCategory:
        print(f"    - {category.value}")
    print("  Departments for allocation: radar, watchtower, command")
    print("  Typical TDM slots: slot_1 ... slot_10")
    print("  Typical FDM bands: band_a, band_b, band_c")


def _allowed_methods() -> list[str]:
    return [m.value for m in ErrorControlMethod]


def _choose_numbered_option(prompt: str, options: list[str], default: str, commands: list[str] | None) -> str:
    print(f"\n{prompt}")
    for idx, option in enumerate(options, start=1):
        suffix = "  [default]" if option == default else ""
        print(f"  {idx}) {option}{suffix}")
    while True:
        token = _script_or_input(commands, "choose number or value> ", default_when_empty=str(options.index(default) + 1) if commands is not None else None)
        if not token:
            return default
        if token.isdigit() and 1 <= int(token) <= len(options):
            return options[int(token) - 1]
        if token in options:
            return token
        print(f"Invalid choice. Enter 1-{len(options)} or one of: {', '.join(options)}")


def _read_int_range(prompt: str, default: int | None, min_value: int, max_value: int, commands: list[str] | None, *, allow_none: bool = False) -> int | None:
    shown_default = "none" if default is None else str(default)
    while True:
        token = _script_or_input(commands, f"{prompt} [{shown_default}]> ", default_when_empty=shown_default if commands is not None else None)
        if token == "":
            return default
        if allow_none and token.lower() in {"none", "off", "null"}:
            return None
        try:
            value = int(token)
        except ValueError:
            print("Please enter an integer" + (" or 'none'." if allow_none else "."))
            continue
        if min_value <= value <= max_value:
            return value
        print(f"Out of range. Enter a value from {min_value} to {max_value}.")


def _read_bool_step(prompt: str, explanation: str, default: bool, commands: list[str] | None) -> bool:
    print("\n" + prompt)
    print("  " + explanation)
    print("  Allowed values: yes/no, on/off, true/false, 1/0")
    while True:
        token = _script_or_input(commands, f"value [{'on' if default else 'off'}]> ", default_when_empty="on" if default and commands is not None else "off" if commands is not None else None)
        if token == "":
            return default
        lowered = token.lower()
        if lowered in {"1", "true", "yes", "y", "on", "enable", "enabled"}:
            return True
        if lowered in {"0", "false", "no", "n", "off", "disable", "disabled"}:
            return False
        print("Invalid value. Use yes/no or on/off.")


def _read_allocation_step(title: str, explanation: str, current_alloc: dict[str, float], commands: list[str] | None) -> dict[str, float]:
    print("\n" + title)
    print("  " + explanation)
    print("  Enter non-negative numeric weights. They will be normalized automatically.")
    print("  Range: each weight can be 0.0 to 10.0. Total must be greater than zero.")
    base = {"radar": 1/3, "watchtower": 1/3, "command": 1/3}
    base.update({k: float(v) for k, v in (current_alloc or {}).items() if k in base})
    while True:
        out = {}
        for dept in ["radar", "watchtower", "command"]:
            while True:
                token = _script_or_input(commands, f"{dept} weight [{base[dept]:.3f}]> ", default_when_empty=str(base[dept]) if commands is not None else None)
                if token == "":
                    value = base[dept]
                    break
                try:
                    value = float(token)
                except ValueError:
                    print("Please enter a numeric value between 0.0 and 10.0.")
                    continue
                if 0.0 <= value <= 10.0:
                    break
                print("Out of range. Use 0.0 to 10.0.")
            out[dept] = value
        total = sum(out.values())
        if total > 0:
            normalized = {k: v / total for k, v in out.items()}
            print("  Normalized allocation:", {k: round(v, 4) for k, v in normalized.items()})
            return normalized
        print("At least one department must receive a positive share. Please enter the allocation again.")


def _read_avoid_list_step(title: str, explanation: str, valid_values: list[str], current_values: list[str], commands: list[str] | None) -> list[str]:
    print("\n" + title)
    print("  " + explanation)
    print("  Allowed values: none, or comma-separated values from: " + ", ".join(valid_values))
    default = ",".join(current_values) if current_values else "none"
    while True:
        token = _script_or_input(commands, f"values [{default}]> ", default_when_empty=default if commands is not None else None)
        if token == "":
            return list(current_values)
        if token.lower() in {"none", "off", "clear", ""}:
            return []
        values = [part.strip() for part in token.split(",") if part.strip()]
        invalid = [v for v in values if v not in valid_values]
        if not invalid:
            return values
        print("Invalid value(s): " + ", ".join(invalid))


def _legacy_preset_command_mode(current, commands: list[str] | None, preset_name: str | None) -> None:
    print("\nOperation Fogline Custom Preset Builder - command mode")
    print("=" * 60)
    print("Type 'help' for commands and 'save <name>' or 'done' when finished.")
    while True:
        cmd = _script_or_input(commands, "preset-builder> ", default_when_empty="done" if commands is not None else None)
        if not cmd:
            continue
        parts = cmd.split()
        action = parts[0].lower()
        try:
            if action == "help":
                print("""
Commands:
  show
  set mux <tdm|fdm>
  set priority <low|medium|high|critical> <method>
  set category <category_name> <method>
  set strictness <normal|strict|very_strict>
  set compact <on|off>
  set suppress_watchtower <on|off>
  set watchtower_limit <none|0|1|2|...>
  set retransmit <priority> <attempts>
  set tdm_alloc <dept> <share>
  set fdm_alloc <dept> <share>
  normalize_alloc
  avoid slot <slot_id|none>
  avoid band <band_id|none>
  save <custom_name>
  done
""")
            elif action == "show":
                _print_strategy_summary(current)
            elif action == "set" and len(parts) >= 3:
                target = parts[1].lower()
                if target == "mux":
                    current.multiplexing_mode = MultiplexingMode(parts[2].lower())
                elif target == "priority" and len(parts) >= 4:
                    current.error_control_by_priority[parts[2].lower()] = ErrorControlMethod(parts[3].lower())
                elif target == "category" and len(parts) >= 4:
                    current.error_control_by_category[parts[2].lower()] = ErrorControlMethod(parts[3].lower())
                elif target == "strictness":
                    current.receiver_strictness = parts[2]
                elif target == "compact":
                    current.use_compact_emergency_mode = _bool_from_token(parts[2])
                elif target == "suppress_watchtower":
                    current.suppress_routine_watchtower = _bool_from_token(parts[2])
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
                current.tdm_allocation = _normalize_alloc_dict(current.tdm_allocation)
                current.fdm_allocation = _normalize_alloc_dict(current.fdm_allocation)
                print("Normalized TDM/FDM allocation shares.")
            elif action == "avoid" and len(parts) >= 3:
                if parts[1].lower() == "slot":
                    current.avoid_slots = [] if parts[2].lower() == "none" else [parts[2]]
                elif parts[1].lower() == "band":
                    current.avoid_bands = [] if parts[2].lower() == "none" else [parts[2]]
            elif action == "save" and len(parts) >= 2:
                current.name = parts[1]
                path = save_custom_strategy(current)
                print(f"Saved custom preset '{current.name}' to {path}")
            elif action in {"done", "finish", "exit"}:
                if current.name in all_strategy_names() or preset_name:
                    if preset_name:
                        current.name = preset_name
                    path = save_custom_strategy(current)
                    print(f"Saved custom preset '{current.name}' to {path}")
                return
            else:
                print("Unknown command. Type help.")
        except Exception as exc:
            print(f"Command failed: {exc}")


def _guided_preset_wizard(current, base_strategy: str, preset_name: str | None, commands: list[str] | None) -> None:
    print("\nOperation Fogline Guided Custom Preset Wizard")
    print("=" * 72)
    print(f"Base strategy: {base_strategy}")
    print("This wizard edits one configuration area at a time. Every step shows the allowed modes/ranges")
    print("and a short explanation of how the setting changes simulator behavior.")
    _print_capabilities()

    # Step 1: identity.
    print("\nStep 1/13 - Preset identity")
    print("  This name is what learners choose later from the dashboard or --strategy.")
    if not preset_name:
        entered = _script_or_input(commands, f"preset name [{current.name}_custom]> ", default_when_empty=f"{current.name}_custom" if commands is not None else None)
        if entered:
            current.name = entered.strip()
        else:
            current.name = f"{current.name}_custom"
    else:
        current.name = preset_name
    desc = _script_or_input(commands, f"short description [{current.description}]> ", default_when_empty=current.description if commands is not None else None)
    if desc:
        current.description = desc

    # Step 2: multiplexing.
    print("\nStep 2/13 - Multiplexing mode")
    print("  TDM shares the link with time slots. FDM shares it with frequency/band partitions.")
    current.multiplexing_mode = MultiplexingMode(_choose_numbered_option(
        "Choose the active multiplexing module", [m.value for m in MultiplexingMode], current.multiplexing_mode.value, commands
    ))

    # Step 3: receiver strictness.
    print("\nStep 3/13 - Receiver strictness")
    print("  normal: accepts valid frames normally. strict/very_strict reject ambiguity more aggressively, especially for Radar/Command.")
    current.receiver_strictness = _choose_numbered_option(
        "Choose receiver decision strictness", ["normal", "strict", "very_strict"], current.receiver_strictness, commands
    )

    # Step 4: priority error control.
    print("\nStep 4/13 - Error control by priority")
    print("  This controls the default protection used for low/medium/high/critical messages.")
    print("  Range/modes: " + ", ".join(_allowed_methods()))
    print("  Note: hamming_secded is automatically restricted to compact emergency codes; invalid normal-frame use falls back safely.")
    for priority in [p.value for p in Priority]:
        default = current.error_control_by_priority.get(priority, ErrorControlMethod.CHECKSUM16).value
        current.error_control_by_priority[priority] = ErrorControlMethod(_choose_numbered_option(
            f"Method for {priority} priority", _allowed_methods(), default, commands
        ))

    # Step 5: category overrides.
    print("\nStep 5/13 - Error control by message category")
    print("  Category overrides can make Radar alerts or emergency codes use a different method than their priority default.")
    print("  Choose methods for each category. Press Enter to keep the shown default in manual mode.")
    for category in [c.value for c in MessageCategory]:
        default = current.error_control_by_category.get(category, ErrorControlMethod.CHECKSUM16).value
        current.error_control_by_category[category] = ErrorControlMethod(_choose_numbered_option(
            f"Method for category {category}", _allowed_methods(), default, commands
        ))

    # Step 6: retransmission.
    print("\nStep 6/13 - Retransmission limits")
    print("  This controls how many retries each priority can use. Higher values improve eventual delivery but can create congestion.")
    print("  Allowed range: 0 to 5 attempts per priority.")
    for priority in [p.value for p in Priority]:
        default = int(current.retransmission_limits_by_priority.get(priority, 1))
        current.retransmission_limits_by_priority[priority] = _read_int_range(
            f"max attempts for {priority}", default, 0, 5, commands
        )

    # Step 7: compact emergency mode.
    print("\nStep 7/13 - Compact emergency mode")
    current.use_compact_emergency_mode = _read_bool_step(
        "Enable compact emergency mode?",
        "When enabled, emergency codes use a compact 32-bit protected block and can use SECDED efficiently.",
        current.use_compact_emergency_mode,
        commands,
    )

    # Step 8: Watchtower shaping.
    print("\nStep 8/13 - Watchtower traffic shaping")
    current.suppress_routine_watchtower = _read_bool_step(
        "Suppress routine Watchtower traffic?",
        "Useful during emergencies or overload; critical Watchtower sightings can still be generated by scenario rules.",
        current.suppress_routine_watchtower,
        commands,
    )
    current.watchtower_reports_per_cycle_limit = _read_int_range(
        "Watchtower reports per cycle limit; use 'none' for no limit",
        current.watchtower_reports_per_cycle_limit,
        0,
        5,
        commands,
        allow_none=True,
    )

    # Step 9: TDM allocation.
    current.tdm_allocation = _read_allocation_step(
        "Step 9/13 - TDM department allocation",
        "These shares become real scheduling quotas when TDM is active. More share means that department can transmit more bits per cycle before low/medium traffic is deferred.",
        current.tdm_allocation,
        commands,
    )

    # Step 10: FDM allocation.
    current.fdm_allocation = _read_allocation_step(
        "Step 10/13 - FDM department allocation",
        "These shares represent intended FDM capacity shares and are used by the scheduler when FDM is active.",
        current.fdm_allocation,
        commands,
    )

    # Step 11: avoided resources.
    current.avoid_slots = _read_avoid_list_step(
        "Step 11/13 - Avoided TDM slots",
        "Avoiding slots moves traffic away from known bad time resources. This should change slot usage and error exposure.",
        [f"slot_{i}" for i in range(1, 11)],
        current.avoid_slots,
        commands,
    )
    current.avoid_bands = _read_avoid_list_step(
        "Step 11b/13 - Avoided FDM bands",
        "Avoiding bands moves traffic away from known jammed/noisy frequency resources.",
        ["band_a", "band_b", "band_c"],
        current.avoid_bands,
        commands,
    )

    # Step 12: FDM rigidity.
    print("\nStep 12/13 - Fixed equal FDM mapping")
    current.force_equal_fdm = _read_bool_step(
        "Force equal fixed FDM department-to-band mapping?",
        "This is useful for demonstrating the Scenario 1 FDM rigidity trap. Usually leave off for adaptive custom presets.",
        current.force_equal_fdm,
        commands,
    )

    # Step 13: review and save.
    print("\nStep 13/13 - Review and save")
    _print_strategy_summary(current)
    print("\nSave options: yes/no. Saving writes to configs/custom_strategies.json.")
    save_it = _read_bool_step("Save this preset now?", "Saved presets appear in the dashboard strategy list and can be used in future runs.", True, commands)
    if save_it:
        path = save_custom_strategy(current)
        print(f"Saved custom preset '{current.name}' to {path}")
    else:
        print("Preset was not saved.")


def build_preset_interactive(base_strategy: str, preset_name: str | None = None) -> None:
    """Build and save a reusable custom preset before a scenario run.

    The builder offers a guided wizard for the fields exposed through
    ``StrategyConfig``. The preset controls configuration values only; the
    module algorithms themselves remain in ``student_modules.py``.
    """
    loader = StudentModuleLoader(PROJECT_ROOT)
    current = copy.deepcopy(loader.get_strategy(base_strategy))
    if preset_name:
        current.name = preset_name

    print("""
Custom Preset Builder
=====================
Choose how to build the preset:
  1) Guided step-by-step wizard
  2) Command mode
""")
    choice = input("builder mode [1/2]> ").strip() or "1"
    if choice == "2":
        _legacy_preset_command_mode(current, None, preset_name)
    else:
        _guided_preset_wizard(current, base_strategy, preset_name, None)



class _DashboardNavigationHandled(Exception):
    """Internal control flow for nested dashboard navigation."""


class MainDashboardConsole:
    def __init__(self):
        self.commands = None
        self.scenario = ScenarioId.FIRST_FOG.value
        self.strategy: str | None = None
        self.seed = 42
        self.quiet = False
        self.auto_adapt = False
        self.interactive_freeze = False
        self.manual_freeze_enabled = True
        self.cycle_dashboard = True
        self.cycle_limit: int | None = None
        self.last_result: dict | None = None

    def _read(self, prompt: str = "> ") -> str:
        return _script_or_input(self.commands, prompt, default_when_empty="exit")

    def _read_nested(self, prompt: str) -> str:
        raw = self._read(prompt)
        token = raw.strip().lower()
        if token in {"menu", "main", "main_menu", "home"}:
            self._menu()
            raise _DashboardNavigationHandled()
        if token in {"help", "?"}:
            self._help()
            raise _DashboardNavigationHandled()
        if token == "status":
            self._status()
            raise _DashboardNavigationHandled()
        if token in {"guide", "config_guide", "configuration_guide", "explain"}:
            self._guide()
            raise _DashboardNavigationHandled()
        if token in {"freeze_modes", "freeze_help", "adaptation_modes"}:
            self._freeze_modes()
            raise _DashboardNavigationHandled()
        return raw

    def _default_strategy(self) -> str:
        groups = list_strategies()
        if self.strategy:
            return self.strategy
        scenario_names = groups.get(self.scenario) or groups.get(ScenarioId.FIRST_FOG.value) or []
        return scenario_names[0] if scenario_names else all_strategy_names()[0]

    def _freeze_mode_label(self) -> str:
        if self.auto_adapt:
            return "code-based automatic adaptation"
        if self.interactive_freeze:
            return "automatic threshold freeze dashboard"
        if self.cycle_dashboard and self.manual_freeze_enabled:
            return "manual checkpoint editing enabled"
        if self.cycle_dashboard and not self.manual_freeze_enabled:
            return "continue-only cycle dashboard"
        return "observe/log only"

    def _status(self) -> None:
        print("\nOperation Fogline Dashboard Status")
        print("=" * 72)
        print(f"Scenario              : {self.scenario}")
        print(f"Strategy/preset       : {self._default_strategy()}")
        print(f"Seed                  : {self.seed}")
        print(f"Quiet output          : {self.quiet}")
        print(f"Run mode              : {self._freeze_mode_label()}")
        print(f"Cycle dashboard       : {self.cycle_dashboard}")
        print(f"Manual checkpoint edit: {self.manual_freeze_enabled}")
        print(f"Automatic freeze UI   : {self.interactive_freeze}")
        print(f"Auto adaptation       : {self.auto_adapt}")
        print(f"Cycle limit           : {self.cycle_limit or 'full scenario'}")
        if self.last_result:
            print(f"Last score            : {self.last_result['grading_summary']['score']:.2f}")
            print(f"Last JSON log         : {self.last_result['json_log']}")
            print(f"Last CSV log          : {self.last_result['csv_log']}")
        print("=" * 72)

    def _menu(self) -> None:
        print("""
Operation Fogline Dashboard Menu
================================
  1) List scenarios
  2) List strategies and saved presets
  3) Build a custom preset with the step-by-step wizard
  4) Run a scenario with the Run Wizard
  5) Show recent run logs
  6) Show current settings
  7) Show option guide
  0) Exit

Type `run` for the full run wizard. Type `menu` inside any wizard step to
return here. Type `help` for the full command list.
""")

    def _help(self) -> None:
        print("""
Operation Fogline Dashboard Commands
====================================
  menu                         show the main menu
  scenarios                    list available scenarios
  strategies                   list strategies and saved presets
  preset_wizard                build a preset using the configuration wizard
  run                          configure and start a scenario step by step
  settings                     edit the main run settings from a numbered screen
  status                       show current settings
  guide                        explain run options and configuration fields
  freeze_modes                 explain freeze/adaptation choices
  report                       show the last run summary again
  reports                      list recent run logs
  cli                          print the equivalent command for the current run
  exit                         leave the dashboard

Shortcuts:
  set scenario <scenario_id>
  set strategy <strategy_name>
  set seed <integer>
  set quiet <on|off>
  set cycle_dashboard <on|off>
  set manual_freeze <on|off>
  set interactive_freeze <on|off>
  set auto_adapt <on|off>
  set cycle_limit <integer|none>
""")

    def _guide(self) -> None:
        print("""
Operation Fogline Run Guide
===========================
Scenario
  The exercise environment. It controls the story, channel behavior, cycle
  count, live events, freeze thresholds, and grading criteria.

Strategy / preset
  The communication policy used by the simulator. A strategy chooses error
  control, multiplexing, receiver strictness, retransmission limits, allocation,
  and traffic-shaping settings.

Seed
  The repeatability number. Keep it fixed when comparing two strategies.

Cycle dashboard
  Shows each cycle's messages, frame outcomes, receiver decisions, metric
  deltas, backlog, and freeze information. It is useful while developing and
  analyzing a strategy.

Manual checkpoint editing
  If enabled, a cycle checkpoint can open the configuration editor when you
  type `freeze`, `checkpoint`, or `edit`. Pressing Enter or typing `continue`
  still moves directly to the next cycle.

Continue-only cycle dashboard
  Keeps the cycle explanations visible but prevents mid-run manual editing.

Automatic threshold freeze dashboard
  Opens the configuration editor only when a simulator threshold freeze is
  reached.

Code-based automatic adaptation
  Calls `adapt_strategy(...)` at freeze points. The starter function keeps the
  current strategy unchanged until you implement adaptation logic.
""")

    def _freeze_modes(self) -> None:
        print("""
Freeze and Adaptation Choices
=============================
  1) Manual checkpoint editing enabled
     Continue moves to the next cycle. The editor opens only when requested.

  2) Continue-only cycle dashboard
     Cycle explanations remain visible, but manual editing is blocked.

  3) Automatic threshold freeze dashboard
     The editor opens automatically at threshold freeze points.

  4) Code-based automatic adaptation
     The `adapt_strategy(...)` function decides what to do at freeze points.

  5) Observe/log only
     Freeze points are logged, but no editor opens and no adaptation is applied.
""")

    def _equivalent_cli(self) -> None:
        parts = ["python", "run_simulation.py", "--scenario", self.scenario, "--strategy", self._default_strategy(), "--seed", str(self.seed)]
        if self.quiet:
            parts.append("--quiet")
        if self.auto_adapt:
            parts.append("--auto-adapt")
        if self.interactive_freeze:
            parts.append("--interactive-freeze")
        if self.cycle_dashboard:
            parts.append("--cycle-dashboard")
        if not self.manual_freeze_enabled:
            parts.append("--no-manual-freeze")
        if self.cycle_limit is not None:
            parts += ["--cycle-limit", str(self.cycle_limit)]
        print(" ".join(parts))

    def _run_simulation(self) -> None:
        self.last_result = run_single(
            PROJECT_ROOT,
            self.scenario,
            self._default_strategy(),
            seed=self.seed,
            quiet=self.quiet,
            auto_adapt=self.auto_adapt,
            interactive_freeze=self.interactive_freeze,
            interactive_script=None,
            cycle_dashboard=self.cycle_dashboard,
            cycle_script=None,
            cycle_limit=self.cycle_limit,
            manual_freeze_enabled=self.manual_freeze_enabled,
        )
        _print_run_result(self.last_result)

    def _choose_from_list(self, title: str, options: list[str], current: str | None = None) -> str | None:
        print(f"\n{title}")
        print("-" * 72)
        for idx, option in enumerate(options, 1):
            marker = " *" if option == current else ""
            print(f"  {idx}) {option}{marker}")
        print("  0) keep current / cancel")
        print("Tip: type a number, the exact name, or `menu` to return to the dashboard.")
        raw = self._read_nested("choose> ")
        if not raw or raw == "0":
            return None
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(options):
                return options[index - 1]
            print("Invalid selection.")
            return None
        if raw in options:
            return raw
        print("Unknown selection.")
        return None

    def _select_scenario(self) -> str | None:
        return self._choose_from_list("Select scenario", [s.value for s in ScenarioId], self.scenario)

    def _select_strategy_for_current_scenario(self) -> str | None:
        groups = list_strategies()
        options = list(groups.get(self.scenario, [])) + list(groups.get("custom_presets", []))
        return self._choose_from_list("Select strategy/preset", options, self._default_strategy())

    def _maybe_edit_selected_strategy(self) -> None:
        print("This optional step opens the preset builder before the run starts.")
        answer = self._read_nested("Review/edit this selected strategy before running? [yes/no]> ")
        if not _bool_from_token(answer):
            return
        base = self._default_strategy()
        suggested = f"{base}_edited"
        name = self._read_nested(f"save edited preset as [{suggested}]> ") or suggested
        build_preset_interactive(base, name)
        self.strategy = name

    def _choose_freeze_mode(self) -> None:
        self._freeze_modes()
        choice = self._read_nested("freeze/adaptation choice [1/2/3/4/5]> ") or "1"
        if choice == "1":
            self.auto_adapt = False
            self.interactive_freeze = False
            self.manual_freeze_enabled = True
            self.cycle_dashboard = True
        elif choice == "2":
            self.auto_adapt = False
            self.interactive_freeze = False
            self.manual_freeze_enabled = False
            self.cycle_dashboard = True
        elif choice == "3":
            self.auto_adapt = False
            self.interactive_freeze = True
            self.manual_freeze_enabled = False
            self.cycle_dashboard = True
        elif choice == "4":
            self.auto_adapt = True
            self.interactive_freeze = False
            self.manual_freeze_enabled = False
        elif choice == "5":
            self.auto_adapt = False
            self.interactive_freeze = False
            self.manual_freeze_enabled = False
        else:
            print("Unknown choice; keeping current freeze/adaptation settings.")
        print(f"Selected mode: {self._freeze_mode_label()}")

    def _settings_menu(self) -> None:
        print("""
Current Run Settings
====================
  1) Scenario
  2) Strategy / preset
  3) Freeze/adaptation mode
  4) Cycle dashboard on/off
  5) Manual checkpoint editing on/off
  6) Automatic threshold freeze dashboard on/off
  7) Code-based auto-adaptation on/off
  8) Seed
  9) Cycle limit
 10) Quiet output on/off
  0) Back
""")
        choice = self._read_nested("settings choice> ")
        if choice == "1":
            selected = self._select_scenario()
            if selected:
                self.scenario = selected
                self.strategy = None
        elif choice == "2":
            selected = self._select_strategy_for_current_scenario()
            if selected:
                self.strategy = selected
        elif choice == "3":
            self._choose_freeze_mode()
        elif choice == "4":
            self.cycle_dashboard = not self.cycle_dashboard
        elif choice == "5":
            self.manual_freeze_enabled = not self.manual_freeze_enabled
            if self.manual_freeze_enabled:
                self.cycle_dashboard = True
                self.auto_adapt = False
                self.interactive_freeze = False
        elif choice == "6":
            self.interactive_freeze = not self.interactive_freeze
            if self.interactive_freeze:
                self.manual_freeze_enabled = False
                self.auto_adapt = False
                self.cycle_dashboard = True
        elif choice == "7":
            self.auto_adapt = not self.auto_adapt
            if self.auto_adapt:
                self.manual_freeze_enabled = False
                self.interactive_freeze = False
        elif choice == "8":
            seed = self._read_nested(f"seed [{self.seed}]> ")
            if seed:
                self.seed = int(seed)
        elif choice == "9":
            value = self._read_nested(f"cycle limit or none [{self.cycle_limit or 'none'}]> ")
            if value:
                self.cycle_limit = None if value.lower() in {"none", "off", "full", "0"} else max(1, int(value))
        elif choice == "10":
            self.quiet = not self.quiet
        elif choice in {"", "0", "back"}:
            return
        else:
            print("Unknown settings choice.")
        self._status()

    def _guided_run(self) -> None:
        print("""
Run Wizard
==========
Configure the actual scenario run step by step. Each step explains what the
option affects. Type `menu` at any step to return to the main dashboard.
""")
        print("Step 1/9 — Scenario")
        print("Choose the exercise environment: story, channel behavior, live events, and grading criteria.")
        scenario = self._select_scenario()
        if scenario:
            self.scenario = scenario
            self.strategy = None

        print("\nStep 2/9 — Strategy / preset")
        print("Choose the communication policy that the simulator will call during the run.")
        strategy = self._select_strategy_for_current_scenario()
        if strategy:
            self.strategy = strategy

        print("\nStep 3/9 — Optional preset editing")
        self._maybe_edit_selected_strategy()

        print("\nStep 4/9 — Freeze/adaptation behavior")
        self._choose_freeze_mode()

        print("\nStep 5/9 — Random seed")
        print("The seed makes runs repeatable when comparing different designs.")
        seed = self._read_nested(f"random seed [{self.seed}]> ")
        if seed:
            self.seed = int(seed)

        print("\nStep 6/9 — Cycle dashboard")
        print("Shows cycle-by-cycle engineering details. Keep it on while developing.")
        value = self._read_nested(f"cycle dashboard on/off [{self.cycle_dashboard}]> ")
        if value:
            self.cycle_dashboard = _bool_from_token(value)

        print("\nStep 7/9 — Cycle limit")
        print("Use a small number for a quick demo, or none/full for the complete scenario.")
        value = self._read_nested(f"cycle limit or none [{self.cycle_limit or 'none'}]> ")
        if value:
            self.cycle_limit = None if value.lower() in {"none", "off", "full", "0"} else max(1, int(value))

        print("\nStep 8/9 — Quiet output")
        print("Quiet output hides most educational text. Leave it off for analysis.")
        value = self._read_nested(f"quiet output on/off [{self.quiet}]> ")
        if value:
            self.quiet = _bool_from_token(value)

        print("\nStep 9/9 — Review and start")
        self._status()
        if _bool_from_token(self._read_nested("start run now? [yes/no]> ")):
            self._run_simulation()
        else:
            print("Run setup saved. Choose `run` again when ready.")

    def _guided_preset(self) -> None:
        names = all_strategy_names()
        base = self._choose_from_list("Choose base strategy for custom preset", names, self._default_strategy()) or self._default_strategy()
        name = self._read_nested("new preset name> ")
        if not name:
            print("Preset not created; name is required.")
            return
        build_preset_interactive(base, name)
        self.strategy = name

    def _show_recent_reports(self) -> None:
        print("\nRecent run logs")
        print("=" * 72)
        folder = PROJECT_ROOT / "logs"
        files = sorted([p for p in folder.glob("*.json") if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)[:12]
        if not files:
            print("  no run logs yet")
        for path in files:
            print(f"  - {path.relative_to(PROJECT_ROOT)}")

    def _dispatch(self, cmd: str) -> bool:
        if not cmd:
            return True
        numeric = {"1": "scenarios", "2": "strategies", "3": "guided_preset", "4": "guided_run", "5": "reports", "6": "status", "7": "guide", "0": "exit"}
        if cmd in numeric:
            cmd = numeric[cmd]
        parts = cmd.split()
        action = parts[0].lower()
        try:
            if action == "help":
                self._help()
            elif action == "menu":
                self._menu()
            elif action == "status":
                self._status()
            elif action == "guide":
                self._guide()
            elif action == "freeze_modes":
                self._freeze_modes()
            elif action == "settings":
                self._settings_menu()
            elif action == "scenarios":
                print("\nAvailable scenarios")
                print("=" * 72)
                for scenario in ScenarioId:
                    print(f"  - {scenario.value}")
            elif action in {"strategies", "list_strategies"}:
                _print_strategy_groups()
            elif action in {"run", "guided_run"}:
                self._guided_run()
            elif action in {"guided_preset", "preset_wizard", "build_wizard"}:
                self._guided_preset()
            elif action == "set" and len(parts) >= 3:
                target = parts[1].lower()
                value = parts[2]
                if target == "scenario":
                    self.scenario = ScenarioId(value).value
                    self.strategy = None
                elif target == "strategy":
                    if value not in all_strategy_names():
                        raise ValueError(f"unknown strategy: {value}")
                    self.strategy = value
                elif target == "seed":
                    self.seed = int(value)
                elif target == "quiet":
                    self.quiet = _bool_from_token(value)
                elif target == "cycle_dashboard":
                    self.cycle_dashboard = _bool_from_token(value)
                elif target == "manual_freeze":
                    self.manual_freeze_enabled = _bool_from_token(value)
                elif target == "interactive_freeze":
                    self.interactive_freeze = _bool_from_token(value)
                    if self.interactive_freeze:
                        self.manual_freeze_enabled = False
                elif target == "auto_adapt":
                    self.auto_adapt = _bool_from_token(value)
                    if self.auto_adapt:
                        self.manual_freeze_enabled = False
                        self.interactive_freeze = False
                elif target == "cycle_limit":
                    self.cycle_limit = None if value.lower() in {"none", "off", "full", "0"} else max(1, int(value))
                else:
                    print("Unknown setting. Type help.")
                self._status()
            elif action == "run_current":
                self._run_simulation()
            elif action == "report":
                if self.last_result:
                    _print_run_result(self.last_result)
                else:
                    print("No run has been executed in this dashboard session yet.")
            elif action == "reports":
                self._show_recent_reports()
            elif action == "cli":
                self._equivalent_cli()
            elif action in {"exit", "quit", "q"}:
                print("Leaving Operation Fogline dashboard.")
                return False
            else:
                print("Unknown command. Type help.")
        except _DashboardNavigationHandled:
            return True
        except Exception as exc:
            print(f"Command failed: {exc}")
        return True

    def loop(self) -> None:
        print("\nOperation Fogline Dashboard")
        print("=" * 72)
        print("A console for listing scenarios, building presets, and running simulations.")
        self._menu()
        while True:
            cmd = self._read()
            if not self._dispatch(cmd):
                return

def main() -> None:
    parser = argparse.ArgumentParser(description="Operation Fogline simulator")
    parser.add_argument("--scenario", choices=[s.value for s in ScenarioId], default=ScenarioId.FIRST_FOG.value)
    parser.add_argument("--strategy", default=None, help="Strategy preset name. Use --list-strategies to see choices.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--auto-adapt", action="store_true", help="Call adapt_strategy at freeze points.")
    parser.add_argument("--interactive-freeze", action="store_true", help="Open the configuration dashboard at automatic freeze points.")
    parser.add_argument("--no-manual-freeze", action="store_true", help="Disable manual checkpoint editing while keeping the cycle dashboard usable.")
    parser.add_argument("--list-strategies", action="store_true")
    parser.add_argument("--build-preset", action="store_true", help="Interactively build and save a custom strategy preset before running.")
    parser.add_argument("--base-strategy", default="starter_equal_tdm", help="Base strategy for --build-preset.")
    parser.add_argument("--preset-name", default=None, help="Name to save in --build-preset mode.")
    parser.add_argument("--dashboard", action="store_true", help="Open the comprehensive main dashboard console instead of using CLI flags directly.")
    parser.add_argument("--cycle-dashboard", action="store_true", help="Show the educational per-cycle dashboard with message traces, metric deltas, and manual checkpoint prompts.")
    parser.add_argument("--cycle-limit", type=int, default=None, help="Optional short-run limit for demos or short experiments.")
    args = parser.parse_args()

    if args.dashboard:
        MainDashboardConsole().loop()
        return

    if args.build_preset:
        build_preset_interactive(args.base_strategy, args.preset_name)
        return

    if args.list_strategies:
        _print_strategy_groups()
        return


    strategy = args.strategy
    if strategy is None:
        strategy = list_strategies().get(args.scenario, list_strategies()[ScenarioId.FIRST_FOG.value])[0]
        print(f"No strategy provided; using default: {strategy}")

    result = run_single(
        PROJECT_ROOT,
        args.scenario,
        strategy,
        seed=args.seed,
        quiet=args.quiet,
        auto_adapt=args.auto_adapt,
        interactive_freeze=args.interactive_freeze,
        interactive_script=None,
        cycle_dashboard=args.cycle_dashboard,
        cycle_script=None,
        cycle_limit=args.cycle_limit,
        manual_freeze_enabled=not args.no_manual_freeze,
    )
    _print_run_result(result)


if __name__ == "__main__":
    main()
