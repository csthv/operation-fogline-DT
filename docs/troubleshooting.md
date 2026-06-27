# Troubleshooting

## `python` command not found

Use the Python launcher available on your system, such as:

```bash
python3 dashboard.py
```

or on Windows:

```bash
py dashboard.py
```

## Dashboard exits unexpectedly

Make sure you are running it in a real terminal rather than an output-only panel. Start with:

```bash
python dashboard.py
```

## Unknown strategy name

Run:

```bash
python run_simulation.py --list-strategies
```

or use the dashboard command:

```text
strategies
```

## Logs are missing

Logs are created only after a run completes. Check the `logs/` directory after the dashboard prints `Run complete`.

## A module change has no visible effect

Check that the changed function is actually used by the simulator and that the returned object contains the expected fields. Run with the cycle dashboard enabled and compare JSON/CSV logs before and after the change.

## Custom preset does not behave as expected

A preset changes `StrategyConfig` values. It does not replace the algorithmic logic in `student_modules.py`. If a configuration field should affect behavior, the corresponding module function must read and use that field.
