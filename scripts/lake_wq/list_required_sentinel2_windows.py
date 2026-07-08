"""List required Sentinel-2 windows for selected runoff events and match against local SAFE ZIPs.

Writes:
  outputs/tables/lake_wq_required_sentinel2_windows.csv   — per-event windows + match status
  outputs/tables/lake_wq_event_image_availability.csv     — per-window image availability
  outputs/tables/lake_wq_missing_sentinel2_download_targets.csv — remaining gaps
"""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lake_wq"))

from lake_wq.config import RAW_SAFE_GLOB, SELECTED_EVENTS_PATH, TABLES_DIR

OUT_REQUIRED = TABLES_DIR / "lake_wq_required_sentinel2_windows.csv"
OUT_AVAILABILITY = TABLES_DIR / "lake_wq_event_image_availability.csv"
OUT_MISSING = TABLES_DIR / "lake_wq_missing_sentinel2_download_targets.csv"

PRE_DAYS = 30
POST_DAYS = 21

# --- Helpers ------------------------------------------------------------------

def parse_date_safe(name: str) -> str | None:
    m = re.search(r"MSIL2A_(\d{8})T", name)
    if not m:
        return None
    raw = m.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

def find_local_products(glob_dir: Path) -> list[dict[str, Any]]:
    products = []
    for p in sorted(glob_dir.glob("*.SAFE.zip")):
        d = parse_date_safe(p.name)
        if d is None:
            continue
        sensor = p.name.split("_")[0]
        tile_match = re.search(r"T(\d{2}[A-Z]{3})", p.name)
        tile = tile_match.group(1) if tile_match else ""
        products.append({
            "product_name": p.name,
            "sensing_date": d,
            "sensor": sensor,
            "tile": tile,
        })
    return products

# --- Main --------------------------------------------------------------------

def main() -> int:
    events = pd.read_csv(SELECTED_EVENTS_PATH)
    products = find_local_products(RAW_SAFE_GLOB)

    print(f"Local SAFE products found: {len(products)}")
    for p in products:
        print(f"  {p['sensing_date']}  {p['sensor']}  {p['tile']}  {p['product_name'][:80]}")

    required_rows = []
    availability_rows = []
    missing_rows = []

    for _, ev in events.iterrows():
        eid = ev["event_id"]
        estart = pd.to_datetime(ev["event_start"])
        eend = pd.to_datetime(ev["event_end"])
        dvol = ev.get("delta_volume_m3", "")

        # Pre window: start-30 to start-1
        pre_start = estart - timedelta(days=PRE_DAYS)
        pre_end = estart - timedelta(days=1)

        # Post window: end to end+21
        post_start = eend + timedelta(days=1)
        post_end = eend + timedelta(days=POST_DAYS)

        # Match products
        pre_matches = []
        post_matches = []
        for prod in products:
            sd = pd.to_datetime(prod["sensing_date"])
            if pre_start <= sd <= pre_end:
                pre_matches.append(prod["product_name"])
            if post_start <= sd <= post_end:
                post_matches.append(prod["product_name"])

        pre_found = len(pre_matches) > 0
        post_found = len(post_matches) > 0
        usable = pre_found and post_found

        if usable:
            status = "READY_FOR_ANOMALY"
            reason = f"Pre: {len(pre_matches)} image(s), Post: {len(post_matches)} image(s)"
        elif pre_found and not post_found:
            status = "MISSING_POST_IMAGE"
            reason = f"Pre image(s) available: {pre_matches[0][:60]}... No post image found."
        elif not pre_found and post_found:
            status = "MISSING_PRE_IMAGE"
            reason = f"Post image(s) available: {post_matches[0][:60]}... No pre image found."
        else:
            status = "MISSING_LOCAL_IMAGE"
            reason = "No local Sentinel-2 pre/post images found for this event window."

        required_rows.append({
            "event_id": eid,
            "event_start": estart.strftime("%Y-%m-%d"),
            "event_end": eend.strftime("%Y-%m-%d"),
            "delta_volume_m3": dvol,
            "pre_window_start": pre_start.strftime("%Y-%m-%d"),
            "pre_window_end": pre_end.strftime("%Y-%m-%d"),
            "post_window_start": post_start.strftime("%Y-%m-%d"),
            "post_window_end": post_end.strftime("%Y-%m-%d"),
            "pre_products_found": len(pre_matches),
            "post_products_found": len(post_matches),
            "usable_pair": "YES" if usable else "NO",
            "status": status,
            "reason": reason,
        })

        # Per-image availability rows
        for role, matches in [("pre", pre_matches), ("post", post_matches)]:
            if matches:
                for m in matches:
                    d = parse_date_safe(m)
                    availability_rows.append({
                        "event_id": eid,
                        "role": role,
                        "product_name": m,
                        "sensing_date": d or "",
                        "status": "MATCHED",
                    })
            else:
                win_start = pre_start if role == "pre" else post_start
                win_end = pre_end if role == "pre" else post_end
                availability_rows.append({
                    "event_id": eid,
                    "role": role,
                    "product_name": "",
                    "sensing_date": "",
                    "status": "MISSING",
                })
                # Add to missing targets
                missing_rows.append({
                    "event_id": eid,
                    "missing_role": role,
                    "target_start": win_start.strftime("%Y-%m-%d"),
                    "target_end": win_end.strftime("%Y-%m-%d"),
                    "preferred_tile": "T32TMR",
                    "product_type": "Sentinel-2 L2A",
                    "search_hint": f"Sentinel-2 L2A, T32TMR, cloud <= 30%, {win_start.strftime('%Y-%m-%d')} to {win_end.strftime('%Y-%m-%d')}",
                })

    # Write outputs
    df_req = pd.DataFrame(required_rows)
    df_avail = pd.DataFrame(availability_rows)
    df_missing = pd.DataFrame(missing_rows)

    df_req.to_csv(OUT_REQUIRED, index=False)
    df_avail.to_csv(OUT_AVAILABILITY, index=False)
    df_missing.to_csv(OUT_MISSING, index=False)

    # Summary
    usable_count = sum(1 for r in required_rows if r["usable_pair"] == "YES")
    missing_pre = sum(1 for r in required_rows if r["status"] == "MISSING_PRE_IMAGE")
    missing_post = sum(1 for r in required_rows if r["status"] == "MISSING_POST_IMAGE")
    missing_all = sum(1 for r in required_rows if r["status"] == "MISSING_LOCAL_IMAGE")

    print(f"\n--- Summary ---")
    print(f"Events: {len(required_rows)}")
    print(f"  READY_FOR_ANOMALY:  {usable_count}")
    print(f"  MISSING_PRE_IMAGE:  {missing_pre}")
    print(f"  MISSING_POST_IMAGE: {missing_post}")
    print(f"  MISSING_LOCAL_IMAGE:{missing_all}")
    print(f"Remaining missing windows: {len(missing_rows)}")
    print(f"\nWrote: {OUT_REQUIRED}")
    print(f"Wrote: {OUT_AVAILABILITY}")
    print(f"Wrote: {OUT_MISSING}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
