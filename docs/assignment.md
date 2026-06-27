# Operation Fogline Assignment Guide

## Context

Operation Fogline is a scenario-based communication-system simulator. A coastal operations link carries Radar, Watchtower, and Command traffic through noisy and changing channel conditions. The objective is to design modular transmission logic that protects important messages, uses limited capacity carefully, and produces defensible engineering analysis.

## Provided infrastructure

The package provides:

- scenario loading;
- message generation;
- story/message catalog;
- channel and interference model;
- frame delivery simulation;
- dashboard and run wizard;
- logging and scoring summaries;
- configuration editor for `StrategyConfig` presets;
- starter module scaffold in `student_modules.py`.

## Implementation focus

Complete and improve the functions in `student_modules.py` while keeping the public API compatible with the simulator. The important engineering areas are:

1. frame preparation;
2. error-control attachment;
3. error-control verification;
4. multiplexing and capacity allocation;
5. receiver decision policy;
6. retransmission policy;
7. strategy adaptation.

## Recommended workflow

1. Run the dashboard with `python dashboard.py`.
2. Use `run` to execute a short baseline run with a fixed seed.
3. Open the JSON/CSV logs in `logs/` and identify the main failure modes.
4. Improve one module at a time.
5. Re-run the same scenario and seed.
6. Compare delivery, wrong accepts, missed deadlines, utilization, overhead, and backlog.
7. Document both successful and rejected design choices.

## Deliverables

A complete submission should include:

- updated `student_modules.py`;
- any saved custom presets that are part of the final design;
- a concise engineering report using logs and metrics;
- clear explanation of frame format, error-control method, multiplexing policy, receiver policy, retransmission policy, and adaptation policy.

## Engineering expectations

The strongest work is not just a high score. It should also explain why a design works, what trade-offs were considered, and how the evidence in the logs supports the final decisions.
