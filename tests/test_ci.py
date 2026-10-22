"""Regression checks for the test workflow itself."""

from pathlib import Path

import yaml


def test_ci_runs_pytest_once_with_isolated_temporary_directory():
    """Do not execute the suite twice or erase the runner temporary root."""
    workflow = yaml.safe_load(
        (Path(__file__).parents[1] / ".github/workflows/py-test.yml").read_text(
            encoding="utf-8"
        )
    )
    steps = workflow["jobs"]["tests"]["steps"]
    commands = [
        step["run"] for step in steps if "pytest --basetemp" in step.get("run", "")
    ]
    assert len(commands) == 1
    assert '--basetemp="$RUNNER_TEMP/pytest"' in commands[0]
    assert "--cov" in commands[0]
