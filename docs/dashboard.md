# Dashboard Guide

Start the dashboard with:

```bash
python dashboard.py
```

The dashboard is the recommended way to configure and run Operation Fogline.

## Main commands

```text
menu            show the main menu
run             open the Run Wizard
settings        edit run settings
strategies      list presets
preset_wizard   create a custom StrategyConfig preset
guide           explain run options
freeze_modes    explain freeze/adaptation modes
reports         list local logs
cli             print equivalent CLI command
exit            quit
```

## Run Wizard

The `run` command asks each run option step by step:

1. scenario;
2. strategy or preset;
3. optional preset editing;
4. freeze/adaptation behavior;
5. random seed;
6. cycle dashboard;
7. cycle limit;
8. quiet output;
9. final confirmation.

Type `menu` inside a step to return to the main dashboard.

## Settings screen

The `settings` command edits the same run values without launching a run immediately. This is useful when preparing several experiments.

## Freeze modes

Use `freeze_modes` to compare the available checkpoint behaviors before running a scenario. For most exploratory runs, manual checkpoint editing or continue-only cycle dashboard mode is the easiest starting point.
