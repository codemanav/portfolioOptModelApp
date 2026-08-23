#!/usr/bin/env python3
"""
Batch runner for the 24 offshore-portfolio scenarios (RI / VA / NC-SC).

Posts each scenario to the running backend (the SAME endpoint the GUI's
"Run the Simulation" button uses), one at a time, and writes results into
backend/Portfolios/ exactly as a GUI run would.

HOW TO RUN
----------
1. Make sure the app is up:  docker compose up --build   (leave it running)
2. In a terminal / VS Code:  python run_scenarios.py
3. Walk away. It prints progress and writes a log to run_scenarios_log.txt.
   Each run takes ~20 min, so the full batch is ~8 hours.

RESUMABLE
---------
After each successful run the scenario key is appended to `completed.txt`.
If the batch stops for any reason, just run it again — it skips finished ones.
To force a rerun of everything, delete completed.txt.

Uses only the Python standard library (no pip installs needed).
"""

import json
import os
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
API_URL = "http://localhost:4000/portfolioOptimization"
HERE = os.path.dirname(os.path.abspath(__file__))
COMPLETED_FILE = os.path.join(HERE, "completed.txt")
LOG_FILE = os.path.join(HERE, "run_scenarios_log.txt")
REQUEST_TIMEOUT = 2 * 60 * 60   # 2 hours per run, generous

# --- Design set (container paths, exactly as the app serves them) ----------
WIND = [
    "/app/Tech Outputs/Wind/GenPU_ATB_15MW_2030_EastCoast_2011_2020.npz",
    "/app/Tech Outputs/Wind/GenPU_ATB_18MW_2030_EastCoast_2011_2020.npz",
]
WAVE = [
    "/app/Tech Outputs/Wave/GenPU_Pelamis_EastCoast_2011_2020.npz",
]
KITE = [
    "/app/Tech Outputs/Current/kite_54kW_0.5-0.75mRFS_2011_2020.npz",
    "/app/Tech Outputs/Current/kite_147kW_0.75-1.0mRFS_2011_2020.npz",
    "/app/Tech Outputs/Current/kite_313kW_1.0-1.25mRFS_2011_2020.npz",
]
COAX = [
    "/app/Tech Outputs/Coaxial/coax_600kW_1.0mRFS_2011_2020.npz",
    "/app/Tech Outputs/Coaxial/coax_1000kW_1.5mRFS_2011_2020.npz",
]
TRANSMISSION = {
    300:  "/app/Tech Outputs/Transmission/Transmission_300MW_East Coast.npz",
    1000: "/app/Tech Outputs/Transmission/Transmission_1000MW_East Coast.npz",
    1200: "/app/Tech Outputs/Transmission/Transmission_1200MW_East Coast.npz",
}

# --- Regions (bounding boxes; lat matches the original run folder tags) -----
REGIONS = {
    "RI":   dict(lat_min=40.98, lat_max=41.30, lon_min=-71.13, lon_max=-70.83),  # Revolution Wind
    "VA":   dict(lat_min=36.85, lat_max=37.04, lon_min=-75.31, lon_max=-75.14),  # CVOW
    "NCSC": dict(lat_min=33.37, lat_max=33.52, lon_min=-78.06, lon_max=-77.73),  # Long Bay
}

# --- Cost variants  (percent of baseline; empty = all baseline) ------------
COST = {
    "base":    {},
    "wec50":   {"wave": 50},
    "kite50":  {"kite": 50},
    "kite150": {"kite": 150},
}

# --- Scenario matrix (24 total) --------------------------------------------
TRANS_CAPS = [300, 1000, 1200]
SCENARIOS = []
def _add(region, variants):
    for cap in TRANS_CAPS:
        for v in variants:
            SCENARIOS.append((region, cap, v))
_add("RI",   ["base", "wec50"])            # 6
_add("VA",   ["base", "wec50", "kite50"])  # 9
_add("NCSC", ["base", "wec50", "kite150"]) # 9
# total = 24


def build_payload(region, cap, variant):
    return {
        "wind": WIND, "wave": WAVE, "kite": KITE, "coaxial": COAX,
        "transmission": [TRANSMISSION[cap]],
        "state": "",
        "box": REGIONS[region],
        "ocean_current_depths": [50],
        "cost_adjust": COST[variant],
        "lcoe_min": 60, "lcoe_max": 120, "lcoe_step": 10,
        "max_system_radius": 30,
        "WindTurbinesPerSite": 4, "KiteTurbinesPerSite": 390,
        "WaveTurbinesPerSite": 300, "CoaxialTurbinesPerSite": 390,
        "max_wind": 2, "min_wind": 1,
        "max_wave": 1, "min_wave": 1,
        "max_kite": 2, "min_kite": 1,
        "max_coaxial": 2, "min_coaxial": 1,
        "start_year": 2016, "end_year": 2018,
    }


def log(msg):
    line = time.strftime("%H:%M:%S") + "  " + msg
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_completed():
    if not os.path.exists(COMPLETED_FILE):
        return set()
    with open(COMPLETED_FILE, encoding="utf-8") as f:
        return set(l.strip() for l in f if l.strip())


def mark_completed(key):
    with open(COMPLETED_FILE, "a", encoding="utf-8") as f:
        f.write(key + "\n")


def post(payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    completed = load_completed()
    total = len(SCENARIOS)
    log(f"=== Batch start: {total} scenarios ({len(completed)} already done) ===")
    t_batch = time.time()
    failures = []

    for i, (region, cap, variant) in enumerate(SCENARIOS, 1):
        key = f"{region}_{cap}_{variant}"
        if key in completed:
            log(f"[{i}/{total}] SKIP {key} (already completed)")
            continue

        log(f"[{i}/{total}] RUN  {key}  (box {REGIONS[region]['lat_min']}-{REGIONS[region]['lat_max']}, "
            f"transmission {cap}MW, cost {COST[variant] or 'baseline'})")
        t0 = time.time()
        status, body = post(build_payload(region, cap, variant))
        dt = time.time() - t0

        if status == 200:
            try:
                ids = json.loads(body).get("portfolio_ids", [])
            except Exception:
                ids = []
            log(f"        OK ({dt/60:.1f} min)  ->  {ids}")
            mark_completed(key)
        else:
            log(f"        FAILED (HTTP {status}, {dt/60:.1f} min): {body[:300]}")
            log(f"        Skipping and continuing; re-run later to retry this one.")
            failures.append(key)

    if failures:
        log(f"=== Batch done in {(time.time()-t_batch)/3600:.1f} h. "
            f"{total-len(failures)-len(completed)} ok this run, {len(failures)} failed: {failures}. Re-run to retry. ===")
    else:
        log(f"=== Batch complete, all scenarios OK in {(time.time()-t_batch)/3600:.1f} h ===")


if __name__ == "__main__":
    main()
