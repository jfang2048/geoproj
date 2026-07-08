"""Summarize ARPA Lake Varese analytical observations as context only."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import re

import pandas as pd

from lake_wq.config import ROOT, ARPA_WQ_PATH, CONTEXT_PATH, CONTEXT_COLUMNS
from lake_wq.io import ensure_lake_wq_dirs, write_csv
from pipeline_utils import StepLog, append_run_log, register_generated_dataset, update_backlog


def _parse_numeric_value(value: Any) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip().replace(",", ".")
    text = re.sub(r"^[<>≤≥= ]+", "", text)
    text = re.sub(r"[^0-9eE+\-.]", "", text)
    if text in {"", ".", "-"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _parameter_group(param: Any) -> str | None:
    text = str(param).lower()
    if "clorofilla" in text or "chlorophyll" in text:
        return "chlorophyll_a_context"
    if "trasparenza" in text or "secchi" in text:
        return "secchi_transparency_context"
    if "torbid" in text or "turbid" in text:
        return "turbidity_context"
    if "solidi" in text and "sosp" in text:
        return "suspended_solids_context"
    if "fosforo totale" in text:
        return "total_phosphorus_context"
    if "ortofosfato" in text:
        return "orthophosphate_context"
    if "fosforo" in text:
        return "phosphorus_context"
    if "ossigeno disciolto" in text:
        return "dissolved_oxygen_context"
    if "ossigeno" in text and "satur" in text:
        return "oxygen_saturation_context"
    if "temperatura" in text:
        return "water_temperature_context"
    if "azoto totale" in text:
        return "total_nitrogen_context"
    if "azoto ammoniacale" in text:
        return "ammonium_context"
    if "azoto nitrico" in text:
        return "nitrate_context"
    return None


def summarize_analytical_context() -> pd.DataFrame:
    ensure_lake_wq_dirs()
    if not ARPA_WQ_PATH.exists() or ARPA_WQ_PATH.stat().st_size == 0:
        out = pd.DataFrame(columns=CONTEXT_COLUMNS)
        write_csv(CONTEXT_PATH, out, CONTEXT_COLUMNS)
        return out
    df = pd.read_csv(ARPA_WQ_PATH)
    if df.empty:
        out = pd.DataFrame(columns=CONTEXT_COLUMNS)
        write_csv(CONTEXT_PATH, out, CONTEXT_COLUMNS)
        return out
    if "PARAMETRO" not in df.columns:
        raise ValueError("ARPA lake analytical table must contain PARAMETRO")
    df = df.copy()
    df["parameter_group"] = df["PARAMETRO"].map(_parameter_group)
    df = df[df["parameter_group"].notna()].copy()
    if df.empty:
        out = pd.DataFrame(columns=CONTEXT_COLUMNS)
        write_csv(CONTEXT_PATH, out, CONTEXT_COLUMNS)
        return out
    df["date"] = pd.to_datetime(df.get("DATA CAMPIONAMENTO"), errors="coerce")
    df["period"] = df["date"].dt.year.astype("Int64").astype(str)
    df.loc[df["period"].eq("<NA>"), "period"] = "unknown"
    df["numeric_value"] = df.get("VALORE", pd.Series(dtype=object)).map(_parse_numeric_value)

    rows: list[dict[str, Any]] = []
    group_cols = ["period", "parameter_group", "PARAMETRO", "UM"]
    for (period, group, param, unit), sub in df.groupby(group_cols, dropna=False):
        vals = sub["numeric_value"].dropna()
        station_names = []
        for _, r in sub.iterrows():
            bits = [str(r.get(c, "")).strip() for c in ["LAGO", "COMUNE", "Codice Stazione"] if str(r.get(c, "")).strip()]
            if bits:
                station_names.append(" / ".join(bits))
        rows.append(
            {
                "period": period,
                "parameter_group": group,
                "parameter": param,
                "unit": unit,
                "station_names": "; ".join(sorted(set(station_names))),
                "station_codes": "; ".join(sorted(set(str(x) for x in sub.get("Codice Stazione", pd.Series(dtype=str)).dropna()))),
                "depth_descriptions": "; ".join(sorted(set(str(x) for x in sub.get("Descrizione Profondità", pd.Series(dtype=str)).dropna()))),
                "sample_count": int(len(sub)),
                "date_min": sub["date"].min().strftime("%Y-%m-%d") if pd.notna(sub["date"].min()) else "",
                "date_max": sub["date"].max().strftime("%Y-%m-%d") if pd.notna(sub["date"].max()) else "",
                "value_min": float(vals.min()) if not vals.empty else "",
                "value_median": float(vals.median()) if not vals.empty else "",
                "value_mean": float(vals.mean()) if not vals.empty else "",
                "value_max": float(vals.max()) if not vals.empty else "",
                "context_note": (
                    "ARPA lake analytical observations are context only. They are not forced into correlation with runoff events "
                    "unless date/station design is suitable, and they do not calibrate Sentinel-2 proxies or runoff estimates."
                ),
            }
        )
    out = pd.DataFrame(rows, columns=CONTEXT_COLUMNS).sort_values(["period", "parameter_group", "parameter"])
    write_csv(CONTEXT_PATH, out, CONTEXT_COLUMNS)
    register_generated_dataset(
        "lake_wq_analytical_context_by_period",
        "Lake Varese analytical water-quality context by period",
        "lake_water_quality_context_only",
        CONTEXT_PATH,
        "processed",
        crs="n/a",
        notes="Summarizes ARPA lake variables as context only; not runoff correlation, calibration, or causal attribution.",
    )
    update_backlog({"F017": "PARTIAL"}, "Summarized ARPA Lake Varese analytical observations as context only.", Path(__file__).name)
    append_run_log(
        StepLog(
            script="scripts/lake_wq/compute_analytical_context.py",
            task="Summarize ARPA Lake Varese analytical observations as context only.",
            inputs=[str(ARPA_WQ_PATH.relative_to(ROOT))],
            outputs=[str(CONTEXT_PATH.relative_to(ROOT))],
            status="DONE",
            reason=f"Wrote {len(out)} context rows; no forced runoff/event correlation applied.",
            files_created=[str(CONTEXT_PATH.relative_to(ROOT))],
            qa_checks=["context_only", "station/depth/date fields retained", "no calibration claim"],
            next_action="Use context table in lake WQ closure figures/docs.",
        )
    )
    print(f"Analytical context rows: {len(out)} -> {CONTEXT_PATH.relative_to(ROOT)}")
    return out


def main() -> int:
    summarize_analytical_context()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
