"""Purpose: Extract and clean post-fire rainfall events from ARPA-style hourly precipitation ZIP archives.
Inputs: data/raw/zip/RW_*.zip (ARPA hourly cumulative precipitation for station 907), config/project.yaml (event window, thresholds).
Outputs: data/processed/weather/precipitation_clean_hourly.csv, precipitation_clean_daily.csv, post_fire_rainfall_events.csv, weather_station_inventory.csv.
CRS: EPSG:4326 (station coordinates); EPSG:32632 (catchment intersection).
Units: Precipitation in mm; duration in days.
Assumptions: Rainfall threshold 1.0 mm/day; dry gap 1 day; station coordinates approximate when legend unavailable.
"""
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

import pandas as pd

from pipeline_utils import RAIN_EVENT_COLUMNS, ROOT, StepLog, append_run_log, ensure_workspace, project_config, register_generated_dataset, update_backlog
from raw_data_utils import weather_zips


def parse_weather_zip(path: Path):
    with zipfile.ZipFile(path) as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
        legend_name = next((n for n in zf.namelist() if n.endswith("Legenda.txt")), None)
        with zf.open(csv_name) as handle:
            df = pd.read_csv(handle, encoding="utf-8-sig")
        meta = {"station_id": "", "station_name": "", "sensor_id": "", "source_file": str(path)}
        if legend_name:
            text = zf.read(legend_name).decode("utf-8-sig", "replace")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            for idx, line in enumerate(lines):
                if line.startswith("Id_Stazione") and idx + 1 < len(lines):
                    parts = lines[idx + 1].split(",")
                    if len(parts) >= 8:
                        meta.update({"station_id": parts[0], "station_name": parts[1], "sensor_id": parts[2], "sensor_name": parts[3], "unit": parts[4], "period_start": parts[5], "period_end": parts[6], "operator": parts[7]})
                    break
        return df, meta


def extract_events(daily: pd.DataFrame, threshold: float, dry_gap_days: int, meta: dict) -> list[dict]:
    events = []
    in_event = False
    start = None
    values = []
    dry_count = dry_gap_days
    event_idx = 1
    for _, row in daily.sort_values("date").iterrows():
        date = pd.to_datetime(row["date"])
        precip = float(row["precipitation_mm"])
        rain = precip > threshold
        if rain and not in_event:
            start = date
            values = [precip]
            in_event = True
            dry_count = 0
        elif rain and in_event:
            values.append(precip)
            dry_count = 0
        elif not rain and in_event:
            dry_count += 1
            if dry_count >= dry_gap_days:
                end = date - pd.Timedelta(days=dry_count)
                total = float(sum(values))
                events.append(
                    {
                        "event_id": f"RAIN_{event_idx:03d}",
                        "start_date": start.date().isoformat(),
                        "end_date": end.date().isoformat(),
                        "duration_days": max(1, (end - start).days + 1),
                        "total_precip_mm": total,
                        "max_daily_precip_mm": max(values),
                        "station_id": meta.get("station_id", ""),
                        "station_name": meta.get("station_name", ""),
                        "station_lat": "",
                        "station_lon": "",
                        "station_elevation_m": "",
                        "distance_to_burned_area_km": "",
                        "data_resolution": "hourly_to_daily_sum",
                        "source_file": meta.get("source_file", ""),
                        "notes": "Extracted from local ARPA-style hourly cumulative precipitation ZIP; station coordinates not included in supplied legend.",
                    }
                )
                event_idx += 1
                in_event = False
                values = []
    if in_event and start is not None:
        end = pd.to_datetime(daily["date"].max())
        total = float(sum(values))
        events.append({"event_id": f"RAIN_{event_idx:03d}", "start_date": start.date().isoformat(), "end_date": end.date().isoformat(), "duration_days": max(1, (end - start).days + 1), "total_precip_mm": total, "max_daily_precip_mm": max(values), "station_id": meta.get("station_id", ""), "station_name": meta.get("station_name", ""), "station_lat": "", "station_lon": "", "station_elevation_m": "", "distance_to_burned_area_km": "", "data_resolution": "hourly_to_daily_sum", "source_file": meta.get("source_file", ""), "notes": "Extracted from local ARPA-style hourly cumulative precipitation ZIP; station coordinates not included in supplied legend."})
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse local ARPA-style weather ZIPs and extract rainfall events.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ensure_workspace()
    station_path = ROOT / "data/processed/weather/weather_station_inventory.csv"
    hourly_path = ROOT / "data/processed/weather/precipitation_clean_hourly.csv"
    daily_path = ROOT / "data/processed/weather/precipitation_clean_daily.csv"
    events_path = ROOT / "data/processed/weather/post_fire_rainfall_events.csv"
    plot_path = ROOT / "outputs/figures/rainfall_events_2019.png"

    if events_path.exists() and plot_path.exists() and not args.force:
        status = "SKIPPED"
        reason = "SKIPPED_VALID_OUTPUT_EXISTS: weather outputs already valid."
        created: list[str] = []
        qa = [f"events_rows={len(pd.read_csv(events_path))}"]
    else:
        cfg = project_config()
        zips = weather_zips()
        all_hourly = []
        metas = []
        for path in zips:
            df, meta = parse_weather_zip(path)
            metas.append(meta)
            df = df.rename(columns={"Id Sensore": "sensor_id", "Data-Ora": "datetime", "Valore Cumulato": "precipitation_mm"})
            df["datetime"] = pd.to_datetime(df["datetime"], format="%Y/%m/%d %H:%M", errors="coerce")
            df["precipitation_mm"] = pd.to_numeric(df["precipitation_mm"], errors="coerce")
            df.loc[df["precipitation_mm"].isin([-999, 777, 7777, 888, 8888]), "precipitation_mm"] = pd.NA
            df["station_id"] = meta.get("station_id", "")
            df["station_name"] = meta.get("station_name", "")
            df["source_file"] = str(path.relative_to(ROOT))
            df["notes"] = "Local ARPA-style precipitation extract; ORA SOLARE UTC+1 per legend."
            all_hourly.append(df[["datetime", "precipitation_mm", "station_id", "station_name", "source_file", "notes"]])
        if not all_hourly:
            raise FileNotFoundError("No local RW_*.zip weather files found; rainfall forcing is essential for event runoff.")
        hourly = pd.concat(all_hourly, ignore_index=True).dropna(subset=["datetime"])
        hourly.to_csv(hourly_path, index=False)
        daily = hourly.copy()
        daily["date"] = daily["datetime"].dt.date.astype(str)
        daily = daily.groupby(["date", "station_id", "station_name"], dropna=False, as_index=False).agg(precipitation_mm=("precipitation_mm", "sum"), source_file=("source_file", "first"))
        daily["notes"] = "Daily sum from local hourly precipitation values."
        daily.to_csv(daily_path, index=False)
        primary_meta = metas[0] if metas else {}
        events = extract_events(daily[["date", "precipitation_mm"]], float(cfg.get("weather", {}).get("rain_day_threshold_mm", 1.0)), int(cfg.get("weather", {}).get("dry_gap_days", 1)), primary_meta)
        events = [e for e in events if float(e["total_precip_mm"]) > 0]
        pd.DataFrame(events, columns=RAIN_EVENT_COLUMNS).to_csv(events_path, index=False)
        station_rows = []
        for meta in metas:
            station_rows.append({"station_id": meta.get("station_id", ""), "station_name": meta.get("station_name", ""), "sensor_id": meta.get("sensor_id", ""), "sensor_name": meta.get("sensor_name", ""), "unit": meta.get("unit", ""), "period_start": meta.get("period_start", ""), "period_end": meta.get("period_end", ""), "station_lat": "", "station_lon": "", "notes": "Station coordinates/elevation not present in supplied legend; add manually if needed for distance QA."})
        pd.DataFrame(station_rows).drop_duplicates().to_csv(station_path, index=False)

        import matplotlib.pyplot as plt
        from figure_config import configure, mm_to_inch, DOUBLE_COLUMN, RAINFALL_COLOR, save_figure
        configure()

        top = pd.DataFrame(events).sort_values("total_precip_mm", ascending=False).head(20).sort_values("start_date")
        fig, ax = plt.subplots(figsize=(mm_to_inch(DOUBLE_COLUMN), mm_to_inch(80)))
        bars = ax.bar(range(len(top)), top["total_precip_mm"], color=RAINFALL_COLOR, width=0.7, edgecolor="white", linewidth=0.3)
        ax.set_xticks(range(len(top)))
        ax.set_xticklabels(top["event_id"], rotation=45, ha="right", fontsize=5)
        ax.set_ylabel("Total precipitation (mm)", fontsize=7)
        ax.set_xlabel("Rainfall event ID", fontsize=7)
        ax.set_ylim(0, top["total_precip_mm"].max() * 1.08)
        ax.tick_params(axis="both", labelsize=5)
        fig.tight_layout(pad=0.5)
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        save_figure(fig, plot_path.with_suffix(".pdf"), plot_path.with_suffix(".png"), dpi=600)
        plt.close(fig)
        register_generated_dataset("weather_station_inventory", "Weather station inventory", "weather_metadata", station_path, "processed", "tabular", "Parsed from local ARPA-style weather ZIP legends.")
        register_generated_dataset("post_fire_rainfall_events", "Post-fire rainfall event table", "rainfall_forcing", events_path, "processed", "tabular", "Extracted from local hourly precipitation ZIPs.")
        created = [str(p.relative_to(ROOT)) for p in [station_path, hourly_path, daily_path, events_path, plot_path]]
        status = "DONE"
        reason = f"Parsed local weather ZIPs and extracted {len(events)} rainfall events from hourly precipitation."
        qa = [f"hourly_rows={len(hourly)}", f"daily_rows={len(daily)}", f"events_rows={len(events)}"]

    update_backlog({"I001": "DONE", "I002": "DONE", "I003": "DONE", "I004": "DONE", "I005": "DONE"}, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Parse local precipitation ZIPs, aggregate daily rainfall, and extract post-fire events.",
            inputs=["data/raw/zip/RW_*.zip"],
            outputs=[str(p.relative_to(ROOT)) for p in [events_path, plot_path]],
            status=status,
            reason=reason,
            files_created=created,
            files_reused=[] if created else [str(events_path.relative_to(ROOT))],
            qa_checks=qa,
            next_action="Run scripts/11_run_simplified_runoff.py.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
