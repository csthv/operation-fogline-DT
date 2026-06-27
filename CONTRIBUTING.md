# Contributing

This repository is organized as a course project package. Contributions should preserve the public simulator API and keep the implementation workspace in `student_modules.py` compatible with the documentation.

## Development setup

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Guidelines

- Keep public function names in `student_modules.py` stable.
- Avoid committing generated files from `logs/` or `reports/`.
- Prefer clear, small changes over broad rewrites.
- Update documentation when command-line flags, dashboard behavior, or API contracts change.
- Keep examples neutral and avoid embedding complete final designs in the starter package.

## Before committing

```bash
python -m py_compile dashboard.py run_simulation.py simulator_core.py student_modules.py story_catalog.py
python -m pytest -q
```
