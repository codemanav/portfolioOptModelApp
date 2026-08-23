#!/usr/bin/env python3
"""
Add-on batch: 9 Gulf Stream scenarios off SC (offshore of the Long Bay project).

This is a SEPARATE, self-contained runner (own completed/log files) so it does
NOT interfere with run_scenarios.py or its progress. Box sits offshore of the
Long Bay project (SC), on the near edge of the Gulf Stream (~87-124 km out),
so the ocean-current (kite/coaxial) designs actually have sites.

    python run_gulfstream.py

Same design set / parameters as the main batch. Resumable via
completed_gulfstream.txt. Standard library only.
"""

import json
import os
import time
import urllib.request
import urllib.error

API_URL = "http://localhost:4000/portfolioOptimization"
HERE = os.path.dirname(os.path.abspath(__file__))
COMPLETED_FILE = os.path.join(HERE, "completed_gulfstream.txt")
LOG_FILE = os.path.join(HERE, "run_gulfstream_log.txt")
REQUEST_TIMEOUT = 2 * 60 * 60

WIND = [
    "/app/Tech Outputs/Wind/GenPU_ATB_15MW_2030_EastCoast_2011_2020.npz",
    "/app/Tech Outputs/Wind/GenPU_ATB_18MW_2030_EastCoast_2011_2020.npz",
]
WAVE = ["/app/Tech Outputs/Wave/GenPU_Pelamis_EastCoast_2011_2020.npz"]
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

# SC Gulf Stream box, offshore of the Long Bay project (folder tag: Box33p2m33p7)
# ~87-124 km offshore; the Stream's near edge off SC. 25 current sites.
GULFSTREAM_BOX = dict(lat_min=33.2, lat_max=33.7, lon_min=-77.5, lon_max=-76.8)

COST = {
    "base":    {},
    "wec50":   {"wave": 50},
    "kite150": {"kite": 150},
}

# 9 scenarios: 3 cost variants x 3 transmission sizes
SCENARIOS = [(cap, v) for cap in (300, 1000, 1200) for v in ("base", "wec50", "kite150")]


def build_payload(cap, variant):
    return {
        "wind": WIND, "wave": WAVE, "kite": KITE, "coaxial": COAX,
        "transmission": [TRANSMISSION[cap]],
        "state": "",
        "box": GULFSTREAM_BOX,
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
    log(f"=== Gulf Stream batch start: {total} scenarios ({len(completed)} already done) ===")
    t_batch = time.time()
    failures = []

    for i, (cap, variant) in enumerate(SCENARIOS, 1):
        key = f"GulfStream_{cap}_{variant}"
        if key in completed:
            log(f"[{i}/{total}] SKIP {key} (already completed)")
            continue

        log(f"[{i}/{total}] RUN  {key}  (SC Long Bay offshore Gulf Stream, "
            f"transmission {cap}MW, cost {COST[variant] or 'baseline'})")
        t0 = time.time()
        status, body = post(build_payload(cap, variant))
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
        log(f"=== Gulf Stream batch done in {(time.time()-t_batch)/3600:.1f} h. "
            f"{len(failures)} failed: {failures}. Re-run to retry. ===")
    else:
        log(f"=== Gulf Stream batch complete, all scenarios OK in {(time.time()-t_batch)/3600:.1f} h ===")


if __name__ == "__main__":
    main()
