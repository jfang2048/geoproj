from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_required_scripts_and_configs_exist():
    required = [
        "scripts/00_setup_workspace.py",
        "scripts/01_inventory_existing_data.py",
        "scripts/02_discover_sources.py",
        "scripts/03_download_open_data.py",
        "scripts/04_prepare_spatial_frame.py",
        "scripts/05_prepare_dem.py",
        "scripts/06_discover_sentinel2.py",
        "scripts/07_prepare_burn_severity.py",
        "scripts/08_prepare_landcover.py",
        "scripts/09_prepare_soil.py",
        "scripts/10_prepare_weather.py",
        "scripts/11_run_simplified_runoff.py",
        "scripts/12_generate_outputs.py",
        "scripts/run_pipeline.py",
        "config/project.yaml",
        "config/sources.yaml",
        "config/paths.yaml",
    ]
    missing = [p for p in required if not (ROOT / p).exists()]
    assert not missing, missing


def test_config_keeps_scientific_thresholds_out_of_code_only():
    cfg = yaml.safe_load((ROOT / "config/project.yaml").read_text())
    assert cfg["project"]["crs_working"] == "EPSG:32632"
    assert "dnbr_thresholds" in cfg["burn_classification"]
    assert cfg["runoff"]["model"] == "simplified_scs_cn_screening"


def test_manifest_and_blocker_files_exist():
    assert (ROOT / "qa/evidence/source_manifest.csv").exists()
    assert (ROOT / "qa/evidence/README.md").exists()
    assert (ROOT / "qa/audit/README.md").exists()
