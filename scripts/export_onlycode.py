"""Generate onlycode/ as a clean public export of the GeoProject workflow.

Copies code, webapp, config templates, docs, and tests.
Excludes data, LaTeX, figures, archives, raw outputs, and generated files.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONLYCODE = ROOT / "onlycode"

INCLUDE_DIRS = [
    "scripts", "webapp", "tests",
]

INCLUDE_FILES = [
    "README.md", "environment.yml", "pyproject.toml",
]

EXCLUDE_PATTERNS = [
    "*.png", "*.jpg", "*.jpeg", "*.pdf", "*.pptx", "*.aux", "*.log",
    "*.SAFE", "*.SAFE.zip", "*.tif", "*.gpkg", "*.zip", "*.csv", "*.xlsx",
    "__pycache__", ".pytest_cache", ".streamlit",
    "webapp/run_logs", "webapp/upload_manifest.csv", "webapp/current_parameters.yaml",
    "data/raw", "data/processed", "data/outputs",
    "qa", "latex", "archive", "outputs", "projects",
    ".codex", ".omx",
    "tests/test_lake_wq_closure.py", "tests/test_quantitative_spatial_qa.py",
    "tests/test_outputs.py", "tests/test_verified_automation.py",
    "tests/test_run_pipeline_contract.py",
    # Old project-specific docs (not general manuals)
    "docs/FINAL_PROJECT_AUDIT.md", "docs/LAKE_WQ_CLOSURE_CHANGELOG.md",
    "docs/PROJECT_CN.md", "docs/PRESENTATION_DRAFT_CN_2H.md",
    "docs/SCRIPTS_EXPLANATION_CN.md", "docs/FIGURE_EXPLANATION_GUIDE_CN.md",
    "docs/REPRODUCIBILITY.md", "docs/PROJECT_SUMMARY.md",
    "docs/AI_IMPLEMENTATION_BRIEF_CN.md", "docs/EOA_DOCUMENT_GAP_REVIEW_CN.md",
]

EXPORT_DOCS = {
    "docs/USER_MANUAL.md": (
        "# User manual\n\n"
        "## Setup\n\n"
        "Place input data under `data/raw/zip/`. Copy `config/example_project.yaml` to `config/project.yaml`.\n\n"
        "## Run the workflow\n\n"
        "```bash\n"
        "python scripts/run_pipeline.py\n"
        "python scripts/lake_wq/run_compute_lake_wq.py\n"
        "python scripts/list_required_sentinel2_windows.py\n"
        "```\n\n"
        "## Launch web interface\n\n"
        "```bash\n"
        "streamlit run webapp/app.py --server.headless true\n"
        "```\n\n"
        "## Interpreting results\n\n"
        "All runoff outputs are screening-level and uncalibrated. dNBR is a remote-sensing proxy, "
        "not field soil burn severity. WEPPcloud is a benchmark, not validation of local SCS-CN. "
        "Lake WQ is Python-only; NDTI is the primary turbidity proxy, NDCI is secondary and indirect.\n"
    ),
    "docs/DATA_REQUIREMENTS.md": (
        "# Data requirements\n\n"
        "Place these files under `data/raw/zip/`:\n\n"
        "- DEM / DTM: `.zip` (e.g. `DTM5_RL.zip`)\n"
        "- Fire perimeter: `.zip`, `.gpkg`, or `.shp`\n"
        "- Sentinel-2 L2A: `.SAFE.zip` (e.g. `S2A_MSIL2A_20190110_*.SAFE.zip`)\n"
        "- Land cover: `.zip` or `.gpkg`\n"
        "- Soil / HSG: `.zip`, `.tif`, or `.csv`\n"
        "- Rainfall: `.zip` or `.csv` (e.g. `RW_*.zip`)\n\n"
        "## Sentinel-2 requirements\n\n"
        "- Product level: L2A (MSIL2A). L1C is not supported.\n"
        "- Preferred tile: T32TMR.\n"
        "- At least one pre-event and one post-event scene per runoff event window.\n"
    ),
    "docs/WEB_INTERFACE.md": (
        "# Web interface\n\n"
        "Streamlit dashboard with interactive maps, dynamic charts, and data tables.\n\n"
        "```bash\n"
        "streamlit run webapp/app.py --server.headless true\n"
        "```\n\n"
        "## Navigation\n\n"
        "Overview | Data | Model | Explorer | Results\n\n"
        "The Explorer section shows a base map. Processed spatial layers (catchment, fire, "
        "response units) appear when pipeline outputs are available. A layer status table "
        "reports which files are still needed.\n\n"
        "All charts are generated from CSV/GeoPackage outputs. Static report figures are not used.\n"
    ),
    "docs/TROUBLESHOOTING.md": (
        "# Troubleshooting\n\n"
        "## Map shows no layers\n\n"
        "The Explorer shows a base map even without data. Spatial layers require pipeline outputs "
        "in `data/processed/`. Run the workflow first.\n\n"
        "## MISSING_LOCAL_IMAGE\n\n"
        "No matching Sentinel-2 pre/post scenes for a selected event. Run "
        "`list_required_sentinel2_windows.py` to see which windows are missing, "
        "then download additional L2A scenes from Copernicus Browser.\n\n"
        "## Wrong product level\n\n"
        "Workflow requires Sentinel-2 L2A (MSIL2A). L1C is not supported.\n\n"
        "## CRS mismatch\n\n"
        "All metric processing uses EPSG:32632. Input files must have CRS metadata.\n"
        "Files without CRS cause the pipeline to fail with 'missing CRS metadata'.\n"
    ),
}


def _should_exclude(rel_path: str) -> bool:
    for pat in EXCLUDE_PATTERNS:
        if pat.startswith("*."):
            ext = pat[1:]
            if rel_path.endswith(ext):
                return True
        elif pat in rel_path or rel_path.startswith(pat):
            return True
    return False


def export() -> None:
    # --- Clean onlycode ---
    if ONLYCODE.exists():
        shutil.rmtree(ONLYCODE)
    ONLYCODE.mkdir()

    # --- Copy directories ---
    for d in INCLUDE_DIRS:
        src = ROOT / d
        if not src.exists():
            continue
        for item in src.rglob("*"):
            rel = str(item.relative_to(ROOT))
            if _should_exclude(rel):
                continue
            if item.is_dir():
                (ONLYCODE / rel).mkdir(parents=True, exist_ok=True)
            else:
                (ONLYCODE / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, ONLYCODE / rel)

    # --- Copy individual files ---
    for f in INCLUDE_FILES:
        src = ROOT / f
        if src.exists():
            dst = ONLYCODE / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # --- Copy config templates ---
    cfg_src = ROOT / "config"
    cfg_dst = ONLYCODE / "config"
    cfg_dst.mkdir(parents=True, exist_ok=True)
    for f in ["project.yaml", "sources.yaml", "paths.yaml", "default.yaml", "example_project.yaml"]:
        src = cfg_src / f
        if src.exists():
            shutil.copy2(src, cfg_dst / f)

    # --- Copy existing docs (skip those we overwrite) ---
    docs_src = ROOT / "docs"
    docs_dst = ONLYCODE / "docs"
    docs_dst.mkdir(parents=True, exist_ok=True)
    overwrite_keys = set(EXPORT_DOCS.keys())
    if docs_src.exists():
        for item in docs_src.iterdir():
            if item.is_file() and item.suffix in (".md",):
                rel = f"docs/{item.name}"
                if rel not in overwrite_keys:
                    shutil.copy2(item, docs_dst / item.name)

    # --- Write simplified export docs ---
    for rel_path, content in EXPORT_DOCS.items():
        p = ONLYCODE / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    # --- Write onlycode README ---
    (ONLYCODE / "README.md").write_text(
        "# GeoProject — Post-fire Runoff Screening\n\n"
        "This folder is a code-only public export of the GeoProject workflow.\n"
        "It does not include raw data, processed outputs, LaTeX files, generated figures, or presentations.\n\n"
        "To reproduce results, place required input data in `data/raw/zip/` and run the workflow.\n\n"
        "## Quick start\n\n"
        "```bash\n"
        "conda env create -f environment.yml\n"
        "conda activate geoproject\n"
        "streamlit run webapp/app.py --server.headless true\n"
        "```\n\n"
        "## Documentation\n\n"
        "See `docs/` for user manual, data requirements, web interface guide, and troubleshooting.\n"
    )

    # --- Write .gitignore ---
    (ONLYCODE / ".gitignore").write_text(
        "data/raw/*\ndata/processed/*\ndata/outputs/*\n"
        "!data/raw/.gitkeep\n!data/processed/.gitkeep\n!data/outputs/.gitkeep\n\n"
        "*.SAFE\n*.SAFE.zip\n*.tif\n*.gpkg\n*.zip\n*.csv\n*.xlsx\n*.nc\n"
        "*.png\n*.jpg\n*.jpeg\n*.pdf\n*.pptx\n*.aux\n*.log\n\n"
        "__pycache__/\n.pytest_cache/\n.streamlit/\n"
        "webapp/run_logs/\nwebapp/upload_manifest.csv\nwebapp/current_parameters.yaml\n"
    )

    # --- Create empty data directories ---
    for d in ["data/raw", "data/processed", "data/outputs"]:
        p = ONLYCODE / d
        p.mkdir(parents=True, exist_ok=True)
        (p / ".gitkeep").touch()

    # --- Count ---
    py_files = list(ONLYCODE.rglob("*.py"))
    md_files = list(ONLYCODE.rglob("*.md"))
    print(f"Exported to {ONLYCODE}")
    print(f"  Python files: {len(py_files)}")
    print(f"  Markdown files: {len(md_files)}")
    print("Excluded: data, outputs, LaTeX, figures, archives, generated binaries.")


if __name__ == "__main__":
    export()
