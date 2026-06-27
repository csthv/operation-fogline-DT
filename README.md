# Operation Fogline

**Operation Fogline** is a modular data-transmission simulator for studying frame construction, error control, multiplexing, receiver decisions, retransmission policy, and adaptive communication under changing channel conditions.

| Field | Value |
|---|---|
| University | University of Isfahan |
| Faculty | Faculty of Computer Engineering |
| Course | Data Transmission |
| Project | Operation Fogline |
| Semester | Spring 1405 / 2026 |
| Instructor | Dr. Behrouz Shahgholi |
| Package preparation | Sepehr Rajabi |

The simulator provides the scenario engine, message generator, channel model, dashboard, logging, scoring, and module loader. The implementation workspace is `student_modules.py`, where the required plug-in functions are completed and improved.

## Repository structure

```text
operation_fogline/
├── dashboard.py                         # Dashboard entry point
├── run_simulation.py                    # CLI and dashboard runner
├── simulator_core.py                    # Scenario engine and simulator infrastructure
├── student_modules.py                   # Implementation workspace
├── story_catalog.py                     # Scenario message/story catalog
├── configs/
│   ├── global_config.json
│   ├── grading_config.json
│   ├── custom_strategies.json
│   └── scenarios/
├── docs/
│   ├── assignment.md
│   ├── api.md
│   ├── dashboard.md
│   ├── report_template.md
│   ├── troubleshooting.md
│   ├── operation_fogline_project_brief.tex
│   └── operation_fogline_simulator_api_appendix.tex
├── logs/                                # Local run logs; ignored by git except .gitkeep
├── reports/                             # Local generated reports; ignored by git except .gitkeep
└── tests/                               # Public smoke tests
```

## Requirements

- Python 3.10 or newer
- No runtime third-party Python packages are required for the simulator itself
- `pytest` is only needed for the optional public smoke tests

Install optional development tools:

```bash
python -m pip install -r requirements-dev.txt
```

## Quick start

Open the dashboard:

```bash
python dashboard.py
```

or:

```bash
python run_simulation.py --dashboard
```

From the dashboard, the most useful commands are:

```text
menu            show the main dashboard menu
run             configure and start a scenario with the Run Wizard
settings        edit run settings from a numbered screen
strategies      list starter and saved presets
preset_wizard   build a custom StrategyConfig preset
guide           explain the main run/configuration options
freeze_modes    explain freeze/adaptation choices
reports         list local run logs
cli             print the equivalent command-line run
exit            leave the dashboard
```

The `run` command opens a nine-step Run Wizard:

1. Scenario
2. Strategy / preset
3. Optional preset editing
4. Freeze/adaptation behavior
5. Random seed
6. Cycle-by-cycle educational dashboard
7. Cycle limit
8. Quiet output
9. Review and start

Each step prints a short explanation before it asks for input. Type `menu` inside a wizard step to cancel the current wizard screen and return to the main dashboard.

## Command-line examples

List available strategies:

```bash
python run_simulation.py --list-strategies
```

Run the first scenario with the starter TDM preset:

```bash
python run_simulation.py \
  --scenario scenario_1_first_fog \
  --strategy starter_equal_tdm \
  --seed 42
```

Run with the educational cycle dashboard:

```bash
python run_simulation.py \
  --scenario scenario_1_first_fog \
  --strategy starter_equal_tdm \
  --cycle-dashboard
```

Run a short two-cycle smoke example:

```bash
python run_simulation.py \
  --scenario scenario_1_first_fog \
  --strategy starter_equal_tdm \
  --cycle-limit 2 \
  --quiet
```

## Implementation workspace

The required module API is in `student_modules.py`:

```python
def list_strategies(): ...
def get_strategy(strategy_name): ...
def prepare_frame(message, system_state, strategy_config): ...
def attach_error_control(frame, system_state, strategy_config): ...
def verify_error_control(received_frame, strategy_config): ...
def choose_multiplexing_plan(protected_frames, system_state, queue_state, strategy_config): ...
def decide_received_frame(received_frame, verification_result, system_state, strategy_config): ...
def decide_retransmission(frame_status, message_context, system_state, strategy_config): ...
def adapt_strategy(dashboard_snapshot, current_strategy_config, capabilities): ...
```

The starter implementation is deliberately conservative. It returns valid structures so the simulator can run, but it is not a complete engineering solution. Improve the modules gradually and verify the effect through logs, metrics, and scenario behavior.

## Freeze and adaptation modes

The simulator supports five run modes:

- **Manual checkpoint editing enabled**: after each cycle, `continue` advances directly; typing `freeze`, `checkpoint`, or `edit` opens the configuration editor.
- **Continue-only cycle dashboard**: cycle explanations remain visible, but mid-run editing is blocked.
- **Automatic threshold freeze dashboard**: the configuration editor opens when a threshold freeze is reached.
- **Code-based automatic adaptation**: `adapt_strategy(...)` is called at freeze points.
- **Observe/log only**: freeze points are logged, with no editor and no adaptation.

## Logs and reports

Run logs are written to `logs/` as JSON and CSV files. These files are local artifacts and are ignored by git. The report template in `docs/report_template.md` gives a suggested structure for engineering analysis.

## Public smoke tests

Run the public smoke tests with:

```bash
python -m pytest -q
```

These tests only verify that the starter package imports correctly, exposes the expected API, and can complete a short simulator run.

## Documentation

- `docs/assignment.md` — project overview and expected deliverables
- `docs/api.md` — plug-in API reference
- `docs/dashboard.md` — dashboard usage guide
- `docs/report_template.md` — engineering report template
- `docs/troubleshooting.md` — common setup and runtime issues

## Academic integrity and reproducibility

Use the dashboard logs and simulator metrics to justify design decisions. Keep random seeds fixed when comparing strategies, and change one design factor at a time when preparing engineering analysis.
