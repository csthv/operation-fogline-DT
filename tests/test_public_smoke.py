from pathlib import Path

from simulator_core import ScenarioId, run_single
from student_modules import get_strategy, list_strategies

ROOT = Path(__file__).resolve().parents[1]


def test_starter_strategies_are_available():
    groups = list_strategies()
    for scenario in ScenarioId:
        assert scenario.value in groups
        assert "starter_equal_tdm" in groups[scenario.value]
    assert get_strategy("starter_equal_tdm").name == "starter_equal_tdm"


def test_short_scenario_run_without_saving_logs():
    result = run_single(
        ROOT,
        ScenarioId.FIRST_FOG.value,
        "starter_equal_tdm",
        seed=42,
        quiet=True,
        cycle_limit=2,
        save_logs=False,
    )
    assert result["scenario_id"] == ScenarioId.FIRST_FOG.value
    assert "grading_summary" in result
    assert result["final_metrics"]["generated"] > 0
    assert result["json_log"] is None
    assert result["csv_log"] is None
