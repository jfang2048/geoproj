"""End-to-end synthetic sample pipeline smoke and consistency checks."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

from postfire_runoff.frontend.components.data_loaders import RUNOFF_DELTA, RUNOFF_EVENTS, RUNOFF_UNITS, core_metrics, load_csv_safe

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_OUTPUTS = [
    ROOT / "data/processed/boundary/catchment_utm32.gpkg",
    ROOT / "data/processed/fire_perimeter/fire_perimeter_utm32.gpkg",
    ROOT / "data/processed/burn/burn_severity_proxy_uint8.tif",
    ROOT / "data/processed/model_inputs/runoff_units.gpkg",
    ROOT / "data/processed/weather/post_fire_rainfall_events.csv",
    ROOT / "outputs/tables/runoff_units.csv",
    ROOT / "outputs/tables/runoff_event_summary.csv",
    ROOT / "outputs/tables/runoff_delta_by_event.csv",
    ROOT / "outputs/tables/burn_severity_area_summary.csv",
    ROOT / "outputs/run_metadata.json",
]


def run_cmd(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)


def test_sample_pipeline_outputs_and_consistency():
    assert run_cmd("sample_data/create_sample_data.py").returncode == 0
    result = run_cmd("-m", "postfire_runoff.cli.run_pipeline", "--config", "config/sample.yaml", "--force")
    assert result.returncode == 0, result.stderr
    for path in REQUIRED_OUTPUTS:
        assert path.exists(), path
        assert path.stat().st_size > 0, path

    units_gdf = gpd.read_file(ROOT / "data/processed/model_inputs/runoff_units.gpkg")
    assert len(units_gdf) >= 4
    area_sum = float(units_gdf["area_m2"].sum())
    union_area = float(units_gdf.geometry.union_all().area)
    assert area_sum > 0
    assert area_sum == pytest.approx(union_area, rel=1e-6, abs=1.0)

    summary = pd.read_csv(ROOT / "outputs/tables/runoff_event_summary.csv")
    assert {"event_id", "rainfall_mm", "baseline_runoff_mm", "burned_runoff_mm", "delta_runoff_mm", "delta_volume_m3"}.issubset(summary.columns)
    numeric = summary[["rainfall_mm", "baseline_runoff_mm", "burned_runoff_mm", "delta_runoff_mm", "baseline_volume_m3", "burned_volume_m3", "delta_volume_m3"]]
    assert np.isfinite(numeric.to_numpy()).all()
    assert (summary[["baseline_runoff_mm", "burned_runoff_mm"]] >= 0).all().all()
    assert np.allclose(summary["delta_runoff_mm"], summary["burned_runoff_mm"] - summary["baseline_runoff_mm"])
    assert np.allclose(summary["delta_volume_m3"], summary["burned_volume_m3"] - summary["baseline_volume_m3"])
    assert np.allclose(summary["baseline_volume_m3"], summary["baseline_runoff_mm"] / 1000.0 * summary["response_unit_area_m2"])

    assert load_csv_safe(RUNOFF_UNITS) is not None
    assert load_csv_safe(RUNOFF_EVENTS) is not None
    assert load_csv_safe(RUNOFF_DELTA) is not None
    metrics = core_metrics()
    assert metrics["catchment_area_ha"] is not None
    assert metrics["conservative_max_dq_mm"] is not None

    metadata = json.loads((ROOT / "outputs/run_metadata.json").read_text())
    assert metadata["status"] == "succeeded"
    assert metadata["optional_stages"]["weppcloud"]["status"] == "unavailable"


def test_missing_required_input_causes_nonzero_exit(tmp_path):
    cfg = tmp_path / "missing.yaml"
    cfg.write_text(
        "project: {crs_working: EPSG:32632}\n"
        "inputs:\n"
        "  catchment_boundary: missing/catchment.geojson\n"
        "  fire_perimeter: missing/fire.geojson\n"
        "  burn_severity: missing/burn.geojson\n"
        "  land_cover: missing/land.geojson\n"
        "  hsg: missing/hsg.geojson\n"
        "  rainfall_events: missing/rain.csv\n"
    )
    result = run_cmd("-m", "postfire_runoff.cli.run_pipeline", "--config", str(cfg), "--project-root", str(ROOT))
    assert result.returncode != 0
    assert "Required input" in result.stderr
