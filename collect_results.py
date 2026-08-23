#!/usr/bin/env python3
"""
Collect the key output plots/CSVs from every completed run into one tidy folder.

The backend writes each run's results into backend/Portfolios/<run>/... as it
finishes. This script copies the important files into ./collected_results/,
one subfolder per run, so you have a clean set to browse or share.

Run it anytime — during the batch (to grab what's done so far) or after.
Only uses the Python standard library.

    python collect_results.py
"""

import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PORTFOLIOS = os.path.join(HERE, "backend", "Portfolios")
OUT = os.path.join(HERE, "collected_results")

# Run-level files to grab from each run folder
RUN_LEVEL = ["Plot_EfficientFrontier.png", "Plot_StackedCosts.png", "Summary.csv"]
# Per-LCOE plots to grab (comment out any you don't want)
PER_LCOE = ["Plot_DeploymentMap.png", "Plot_StackedGenByTech.png",
            "Plot_TotalGeneration.png", "Plot_Curtailment.png"]


def main():
    if not os.path.isdir(PORTFOLIOS):
        print("Portfolios folder not found:", PORTFOLIOS)
        return
    os.makedirs(OUT, exist_ok=True)

    runs = 0
    files = 0
    for dirpath, dirnames, filenames in os.walk(PORTFOLIOS):
        if "Summary.csv" not in filenames:
            continue
        runs += 1
        # Name the collected subfolder after the run's path (region/designs/transmission)
        rel = os.path.relpath(dirpath, PORTFOLIOS).replace(os.sep, "__")
        dest = os.path.join(OUT, rel)
        os.makedirs(dest, exist_ok=True)

        for fn in RUN_LEVEL:
            src = os.path.join(dirpath, fn)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(dest, fn)); files += 1

        # per-LCOE subfolders
        for sub in sorted(d for d in dirnames if d.startswith("LCOE_")):
            for fn in PER_LCOE:
                src = os.path.join(dirpath, sub, fn)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(dest, f"{sub}_{fn}")); files += 1

        print("collected:", rel)

    print(f"\nDone. {files} files from {runs} run(s) -> {OUT}")


if __name__ == "__main__":
    main()
