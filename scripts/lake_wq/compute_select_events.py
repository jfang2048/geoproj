"""Select high-runoff events for Python-only lake WQ proxy anomaly screening.

Inputs are existing runoff/rainfall outputs; this script does not recompute the
SCS-CN model or WEPPcloud benchmark.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

from lake_wq.config import (
    ROOT,
    DELTA_PATH,
    RAINFALL_EVENTS_PATH,
    SELECTED_EVENTS_PATH,
    SELECTED_EVENT_COLUMNS,
)
from lake_wq.io import ensure_lake_wq_dirs, read_csv_required, write_csv
from pipeline_utils import StepLog, append_run_log, now_utc, register_generated_dataset, update_backlog


def _first_available(columns: Iterable[str], candidates: list[str]) -> str | None:
    available = set(columns)
    for name in candidates:
        if name in available:
            return name
    return None


def _numeric(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def select_events(top_n: int = 10) -> tuple[pd.DataFrame, str, dict[str, list[str]]]:
    """Return selected events, chosen ranking metric, and inspected columns."""
    top_n = max(5, min(10, int(top_n)))
    delta = read_csv_required(DELTA_PATH, "runoff delta by event")
    events = read_csv_required(RAINFALL_EVENTS_PATH, "post-fire rainfall events")
    inspected = {
        str(DELTA_PATH.relative_to(ROOT)): list(delta.columns),
        str(RAINFALL_EVENTS_PATH.relative_to(ROOT)): list(events.columns),
    }
    if "event_id" not in delta.columns or "event_id" not in events.columns:
        raise ValueError("Both runoff_delta_by_event.csv and post_fire_rainfall_events.csv must contain event_id")
    start_col = _first_available(events.columns, ["event_start", "start_date", "start", "date_start"])
    end_col = _first_available(events.columns, ["event_end", "end_date", "end", "date_end"])
    if start_col is None or end_col is None:
        raise ValueError(f"Rainfall event table must contain event start/end columns; inspected {list(events.columns)}")

    merged = events.merge(delta, on="event_id", how="inner", suffixes=("_event", "_runoff"))
    if merged.empty:
        raise ValueError("No event_id values overlap between rainfall events and runoff delta tables")

    ranking_metric = _first_available(merged.columns, ["delta_volume_m3", "delta_runoff_mm", "total_precip_mm"])
    if ranking_metric is None:
        raise ValueError("Need one of delta_volume_m3, delta_runoff_mm, or total_precip_mm for event ranking")

    merged["_rank_metric"] = _numeric(merged, ranking_metric)
    selected = merged.sort_values(["_rank_metric", "event_id"], ascending=[False, True]).head(top_n).copy()
    selected["selection_rank"] = range(1, len(selected) + 1)
    if ranking_metric == "delta_volume_m3":
        reason = "Primary ranking: largest delta_volume_m3 from runoff_delta_by_event.csv."
    elif ranking_metric == "delta_runoff_mm":
        reason = "Fallback ranking: largest delta_runoff_mm because delta_volume_m3 was unavailable."
    else:
        reason = "Fallback ranking: largest total_precip_mm because runoff-delta metrics were unavailable."
    selected["selection_reason"] = reason

    out = pd.DataFrame()
    out["event_id"] = selected["event_id"].astype(str)
    out["event_start"] = pd.to_datetime(selected[start_col]).dt.strftime("%Y-%m-%d")
    out["event_end"] = pd.to_datetime(selected[end_col]).dt.strftime("%Y-%m-%d")
    for col in ["total_precip_mm", "delta_runoff_mm", "delta_volume_m3", "baseline_runoff_mm", "burned_runoff_mm"]:
        out[col] = selected[col] if col in selected.columns else pd.NA
    out["selection_rank"] = selected["selection_rank"]
    out["selection_reason"] = selected["selection_reason"]
    return out[SELECTED_EVENT_COLUMNS], ranking_metric, inspected


def run(top_n: int = 10) -> pd.DataFrame:
    ensure_lake_wq_dirs()
    selected, metric, inspected = select_events(top_n)
    write_csv(SELECTED_EVENTS_PATH, selected, SELECTED_EVENT_COLUMNS)
    register_generated_dataset(
        "lake_response_selected_events",
        "Selected lake response rainfall events",
        "lake_water_quality_linkage_input",
        SELECTED_EVENTS_PATH,
        "processed",
        crs="n/a",
        notes=(
            "Selected from existing runoff/rainfall outputs for Python-only screening-level Sentinel-2 lake proxy anomaly analysis. "
            f"Ranking metric={metric}; generated {now_utc()}."
        ),
    )
    update_backlog({"F016": "DONE"}, f"Selected {len(selected)} lake response events using ranking metric {metric}.", Path(__file__).name)
    append_run_log(
        StepLog(
            script="scripts/lake_wq/compute_select_events.py",
            task="Select rainfall events for lake water-quality remote-sensing response screening.",
            inputs=[str(DELTA_PATH.relative_to(ROOT)), str(RAINFALL_EVENTS_PATH.relative_to(ROOT))],
            outputs=[str(SELECTED_EVENTS_PATH.relative_to(ROOT))],
            status="DONE",
            reason=f"Selected {len(selected)} events by {metric}; no runoff values were recomputed.",
            files_created=[str(SELECTED_EVENTS_PATH.relative_to(ROOT))],
            qa_checks=["input_columns_inspected", f"ranking_metric={metric}", "screening_selection_only"],
            next_action="Run scripts/lake_wq/compute_rois.py and compute_s2_indices.py.",
        )
    )
    print("Inspected input columns:")
    for path, cols in inspected.items():
        print(f"- {path}: {cols}")
    print(f"Selected {len(selected)} events ranked by {metric} -> {SELECTED_EVENTS_PATH.relative_to(ROOT)}")
    print(selected[["event_id", "event_start", "event_end", "total_precip_mm", "delta_volume_m3", "selection_rank"]].to_string(index=False))
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Select top runoff events for Python-only Lake Varese WQ response screening.")
    parser.add_argument("--top-n", type=int, default=10, help="Number of events to select, clipped to 5-10.")
    args = parser.parse_args()
    run(args.top_n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
