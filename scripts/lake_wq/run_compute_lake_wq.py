"""Run the Python-only Lake Varese water-quality closure compute workflow."""
from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lake_wq.compute_select_events import run as run_select_events
from lake_wq.compute_rois import create_rois
from lake_wq.compute_s2_indices import compute_s2_indices
from lake_wq.compute_zonal_anomalies import compute_zonal_anomalies
from lake_wq.compute_analytical_context import summarize_analytical_context
from lake_wq.config import ROOT
from pipeline_utils import StepLog, append_run_log, update_backlog


def main() -> int:
    print("Python-only Lake Varese WQ closure: local files and Python scripts only; no GEE path.")
    selected = run_select_events(top_n=10)
    rois = create_rois()
    metadata, qa = compute_s2_indices()
    anomalies = compute_zonal_anomalies()
    context = summarize_analytical_context()
    flags = sorted(str(x) for x in qa.get("quality_flag", []).dropna().unique()) if not qa.empty else []
    update_backlog({"F017": "DONE" if "PASS" in flags else "PARTIAL"}, "Ran full Python-only lake WQ compute workflow.", Path(__file__).name)
    append_run_log(
        StepLog(
            script="scripts/lake_wq/run_compute_lake_wq.py",
            task="Run Python-only lake WQ closure compute workflow.",
            inputs=["outputs/tables/runoff_delta_by_event.csv", "outputs/tables/post_fire_rainfall_events.csv", "data/raw/zip/*.SAFE.zip"],
            outputs=[
                "outputs/tables/lake_response_selected_events.csv",
                "data/processed/water_quality/lake_varese_wq_rois_utm32.gpkg",
                "outputs/tables/lake_wq_event_anomalies.csv",
                "outputs/tables/lake_wq_analytical_context_by_period.csv",
                "qa/spatial/lake_wq_remote_sensing_qa.csv",
                "outputs/qa/lake_wq_remote_sensing_qa.csv",
            ],
            status="DONE" if "PASS" in flags else "PARTIAL",
            reason="Python-only workflow completed; missing Sentinel-2 event coverage is reported as QA data limitation where applicable.",
            files_created=[
                "outputs/tables/lake_response_selected_events.csv",
                "data/processed/water_quality/lake_varese_wq_rois_utm32.gpkg",
                "outputs/tables/lake_wq_event_anomalies.csv",
                "outputs/tables/lake_wq_analytical_context_by_period.csv",
                "qa/spatial/lake_wq_remote_sensing_qa.csv",
            ],
            qa_checks=["no GEE calls/files", "EPSG:32632 ROIs", "local SAFE search only", f"QA flags={flags}"],
            next_action="Run scripts/lake_wq/figures/run_lake_wq_figures.py.",
        )
    )
    print("\nSummary")
    print(f"- selected events: {len(selected)} -> outputs/tables/lake_response_selected_events.csv")
    print(f"- ROIs: {len(rois)} -> data/processed/water_quality/lake_varese_wq_rois_utm32.gpkg")
    print(f"- Sentinel-2 image metadata rows: {len(metadata)} -> outputs/intermediate/lake_wq/lake_wq_event_image_metadata.csv")
    print(f"- QA flags: {flags} -> qa/spatial/lake_wq_remote_sensing_qa.csv")
    print(f"- anomaly rows: {len(anomalies)} -> outputs/tables/lake_wq_event_anomalies.csv")
    print(f"- analytical context rows: {len(context)} -> outputs/tables/lake_wq_analytical_context_by_period.csv")
    print("- If local Sentinel-2 event coverage is insufficient, this is reported as a data limitation rather than filled with GEE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
