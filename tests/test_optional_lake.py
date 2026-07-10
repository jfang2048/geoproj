"""Optional lake WQ stage records unavailable status without fake anomalies."""
from pathlib import Path

import pandas as pd

from postfire_runoff.backend.pipeline.lake_wq import OPTIONAL_MISSING_INPUT_EXIT, run_lake_wq

ROOT = Path(__file__).resolve().parents[1]


def test_missing_optional_lake_inputs_write_status_after_sample_run():
    # The sample pipeline test normally creates the event summary; if this test is
    # run alone, create it first.
    if not (ROOT / "outputs/tables/runoff_event_summary.csv").exists():
        from postfire_runoff.backend.pipeline.runoff import run_pipeline
        import sample_data.create_sample_data as sample
        sample.main()
        run_pipeline("config/sample.yaml", force=True)
    result = run_lake_wq("config/sample.yaml")
    assert result.exit_code == OPTIONAL_MISSING_INPUT_EXIT
    assert result.status == "missing_input"
    status = pd.read_csv(result.status_table)
    assert status.loc[0, "numeric_proxy_rows"] == 0
    assert "missing_input" in set(status["status"])
