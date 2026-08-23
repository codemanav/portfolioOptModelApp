#env Gurobi

from flask import Flask, jsonify, send_file, request
from flask_cors import CORS, cross_origin

import csv
import numpy as np
import xarray as xr
import sys
import json
from datetime import datetime, timedelta
from tqdm import tqdm
import time
import os
import io
import shutil
import glob as globmod
import re
from pathlib import Path
import traceback


def _design_short(path):
    """Turn a selected design file path into a short, readable tag for the run
    folder name, e.g.:
        GenPU_ATB_15MW_2030_EastCoast_2011_2020.npz -> ATB_15MW_2030
        GenPU_RM3_EastCoast_2011_2020.npz           -> RM3
        EastCoast_HalfScale_63.62.npz               -> HalfScale_63.62
        kite_Design1_EastCoast_2011_2020.npz        -> kite_Design1
    Strips the GenPU_ prefix and the redundant EastCoast / year-range suffix
    (region + years are already elsewhere in the run id)."""
    s = os.path.splitext(os.path.basename(path))[0]
    if s.startswith("GenPU_"):
        s = s[len("GenPU_"):]
    s = re.sub(r'_?EastCoast(_\d{4}_\d{4})?', '', s)   # drop EastCoast[_year_year]
    s = re.sub(r'_\d{4}_\d{4}$', '', s)                # drop any trailing year range
    s = s.strip('_')
    return s or os.path.splitext(os.path.basename(path))[0]

import Port_Opt_MaxGeneration_EastCoast_EnvConst as _model
from Port_Opt_MaxGeneration_EastCoast_EnvConst import SolvePortOpt_MaxGen_LCOE_Iterator
from GeneralGeoTools_EastCoast import PlotEfficientFrontier, ChangeTimeSpaceResolution
from gurobipy import *

app = Flask(__name__)
CORS(app)

path = Path(__file__).parent

# ---------------------------------------------------------------------------
# Directory layout  (East Coast Model)
# ---------------------------------------------------------------------------
GEOSPATIAL_DATA = str(path / "Geospatial Data")
TECH_DESIGNS    = str(path / "Tech Designs")
RESOURCE_DATA   = str(path / "Resource Data")
TECH_OUTPUTS    = str(path / "Tech Outputs")
INPUT_DATA      = str(path / "InputData")
PORTFOLIOS_DIR  = str(path / "Portfolios")
PLOTS_DIR       = os.path.join(PORTFOLIOS_DIR, "_plots")
ENVIRONMENT_DIR = str(path / "Environment")

os.makedirs(PORTFOLIOS_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs(ENVIRONMENT_DIR, exist_ok=True)
os.makedirs(os.path.join(TECH_OUTPUTS, "Wind"), exist_ok=True)
os.makedirs(os.path.join(TECH_OUTPUTS, "Wave"), exist_ok=True)
os.makedirs(os.path.join(TECH_OUTPUTS, "Wave", "ByState"), exist_ok=True)
os.makedirs(os.path.join(TECH_OUTPUTS, "Wave", "ByState_Uniform"), exist_ok=True)
os.makedirs(os.path.join(TECH_OUTPUTS, "Current"), exist_ok=True)
os.makedirs(os.path.join(TECH_OUTPUTS, "Transmission"), exist_ok=True)
os.makedirs(os.path.join(TECH_OUTPUTS, "Transmission", "ByState"), exist_ok=True)

# ---------------------------------------------------------------------------
# State name utilities
# ---------------------------------------------------------------------------
STATE_DISPLAY_NAMES = {
    "fl": "Florida",       "ga": "Georgia",         "sc": "South_Carolina",
    "nc": "North_Carolina", "va": "Virginia",        "md": "Maryland",
    "de": "Delaware",       "nj": "New_Jersey",      "ny": "New_York",
    "ct": "Connecticut",    "ri": "Rhode_Island",    "ma": "Massachusetts",
    "nh": "New_Hampshire",  "me": "Maine",
}

# Transmission files use spaces instead of underscores for some states
STATE_TRANSMISSION_NAMES = {
    "fl": "Florida",       "ga": "Georgia",         "sc": "South Carolina",
    "nc": "North Carolina", "va": "Virginia",        "md": "Maryland",
    "de": "Delaware",       "nj": "New Jersey",      "ny": "New York",
    "ct": "Connecticut",    "ri": "Rhode Island",    "ma": "Massachusetts",
    "nh": "New Hampshire",  "me": "Maine",
}

def _norm(name):
    """Normalize a name for tolerant matching (drop separators, lowercase)."""
    return name.lower().replace("_", "").replace(" ", "")


def _find_by_state_suffix(directory, token, state_display, subdirs=("",)):
    """Find a .npz under `directory` whose name contains `token` and ENDS with the
    state name (separators ignored). Tolerates provenance tokens in between, e.g.
    GenPU_RM3_lat_40.98_41.3_2016_2018_Virginia.npz. Returns path or None."""
    ntoken, nstate = _norm(token), _norm(state_display)
    for sub in subdirs:
        d = os.path.join(directory, sub) if sub else directory
        if not os.path.isdir(d):
            continue
        for f in sorted(globmod.glob(os.path.join(d, "*.npz"))):
            nb = _norm(os.path.splitext(os.path.basename(f))[0])
            if ntoken in nb and nb.endswith(nstate):
                return f
    return None


# Wind files have inconsistent naming; try exact patterns, then a flexible fallback
def _find_wind_file(turbine_name, state_display):
    """Find wind NPZ for a given turbine and state, handling naming inconsistencies."""
    wind_dir = os.path.join(TECH_OUTPUTS, "Wind")
    # Try several exact naming patterns observed in the East Coast Model
    candidates = [
        os.path.join(wind_dir, f"GenPU_{turbine_name}{state_display}.npz"),         # GenPU_ATB_18MW_2030Virginia.npz
        os.path.join(wind_dir, f"GenPU_{turbine_name}_{state_display}.npz"),        # GenPU_ATB_18MW_2030_Florida.npz
        os.path.join(wind_dir, f"GenPU_{turbine_name}{state_display.replace('_','')}.npz"),  # GenPU_...NewJersey
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # Flexible fallback: contains the turbine id and ends with the state name
    return _find_by_state_suffix(wind_dir, turbine_name, state_display)


def _find_wave_file(device_name, state_display):
    """Find wave NPZ for a given device and state (exact patterns, then flexible)."""
    candidates = [
        os.path.join(TECH_OUTPUTS, "Wave", "ByState_Uniform", f"{state_display}_{device_name}.npz"),
        os.path.join(TECH_OUTPUTS, "Wave", "ByState", f"{state_display}_{device_name}.npz"),
        os.path.join(TECH_OUTPUTS, "Wave", f"{state_display}_{device_name}.npz"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # Flexible fallback: contains the device id and ends with the state name,
    # e.g. GenPU_RM3_lat_40.98_41.3_2016_2018_Virginia.npz
    return _find_by_state_suffix(os.path.join(TECH_OUTPUTS, "Wave"), device_name, state_display,
                                 subdirs=("ByState_Uniform", "ByState", ""))


def _find_kite_file(design_id, state_display, depth_m=100):
    """Find kite/current NPZ for a given design and state."""
    candidates = [
        os.path.join(TECH_OUTPUTS, "Current", "ByState_MaxLCOE120",
                     f"KitePower_Design{design_id}_{state_display}_{depth_m}m.npz"),
        os.path.join(TECH_OUTPUTS, "Current",
                     f"KitePower_Design{design_id}_{state_display}_{depth_m}m.npz"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _find_transmission_file(capacity_mw, state_code):
    """Find transmission NPZ for a given capacity and state."""
    state_name = STATE_TRANSMISSION_NAMES.get(state_code, "")
    candidates = [
        os.path.join(TECH_OUTPUTS, "Transmission", "ByState",
                     f"Transmission_{capacity_mw}MW_{state_name}.npz"),
        os.path.join(TECH_OUTPUTS, "Transmission",
                     f"Transmission_{capacity_mw}MW_{state_name}.npz"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


# ---------------------------------------------------------------------------
# Custom lat/long range support
# ---------------------------------------------------------------------------
# Latitude band covered by each state's data files (from "State Lat Ranges").
STATE_LAT_RANGES = {
    "fl": (24.2, 31.0), "ga": (30.6, 32.2), "sc": (32.0, 34.0),
    "nc": (33.7, 36.6), "va": (36.4, 38.2), "md": (38.0, 38.6),
    "de": (38.4, 39.5), "nj": (38.8, 41.0), "ny": (40.4, 41.5),
    "ct": (41.2, 41.5), "ri": (41.1, 41.5), "ma": (41.1, 42.9),
    "nh": (42.8, 43.3), "me": (43.0, 45.5),
}

# Temp folder for box-filtered design files passed to the optimizer.
BOX_TMP_DIR = os.path.join(PORTFOLIOS_DIR, "_boxfiltered")


def _states_in_lat_range(lat_min, lat_max):
    """State codes whose data latitude band overlaps [lat_min, lat_max]."""
    lo, hi = min(lat_min, lat_max), max(lat_min, lat_max)
    return [code for code, (a, b) in STATE_LAT_RANGES.items() if b >= lo and a <= hi]


def _time_slice_npz(src_path, start_year, end_year, tag):
    """Subset a design .npz to timesteps whose year is within [start_year, end_year].

    Slices TimeList and any array whose first axis == len(TimeList) (e.g. Energy_pu,
    RawResource); spatial arrays like LatLong are left alone. Returns (path, n_steps):
    the original path if there is no time axis or the whole range is kept, a new temp
    file if sliced, or (None, 0) if no timesteps fall inside the range.
    """
    D = np.load(src_path, allow_pickle=True)
    if "TimeList" not in D.files:
        return src_path, -1
    tl = D["TimeList"]
    T = len(tl)
    years = np.array([getattr(t, "year", -1) for t in tl])
    tmask = (years >= start_year) & (years <= end_year)
    n = int(tmask.sum())
    if n == 0:
        return None, 0
    if n == T:
        return src_path, T
    out = {}
    for k in D.files:
        a = D[k]
        arr = np.asarray(a)
        if k != "LatLong" and arr.ndim >= 1 and arr.shape[0] == T:
            out[k] = arr[tmask]
        else:
            out[k] = a
    os.makedirs(BOX_TMP_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(src_path))[0]
    out_path = os.path.join(BOX_TMP_DIR, f"{base}__{tag}_yr.npz")
    np.savez(out_path, **out)
    return out_path, n


# ---------------------------------------------------------------------------
# Whole-coast slicing (port of the notebook's _slice_design)
# ---------------------------------------------------------------------------
def _clean_core(path):
    core = os.path.splitext(os.path.basename(path))[0]
    for suf in ("_EastCoast_2011_2020", "_2011_2020", "_EastCoast"):
        if core.endswith(suf):
            return core[:-len(suf)]
    return core


def _npz_member_shape(npz_path, member):
    """Read one array's shape from an .npz WITHOUT decompressing its data."""
    import zipfile
    from numpy.lib import format as _npf
    with zipfile.ZipFile(npz_path) as z:
        with z.open(member + ".npy") as f:
            major, _minor = _npf.read_magic(f)
            if major == 1:
                shape, _fortran, _dtype = _npf.read_array_header_1_0(f)
            else:
                shape, _fortran, _dtype = _npf.read_array_header_2_0(f)
    return shape


def _slice_design(path, lat_min, lat_max, lon_min, lon_max,
                  start_year, end_year, region_tag, out_dir, depth_m=None):
    """Slice a whole-coast design .npz by year + region (+ ocean-current depth),
    faithful to the notebook's _slice_design. Writes a small temp .npz and returns
    its path. Cached: if the sliced file already exists it is reused, so the large
    source array is only loaded once per (design, region, years, depth)."""
    os.makedirs(out_dir, exist_ok=True)
    base = (f"{_clean_core(path)}_{region_tag}_{start_year}_{end_year}"
            + (f"_{int(depth_m)}m" if depth_m is not None else ""))
    op = os.path.join(out_dir, f"{base}.npz")
    if os.path.isfile(op):
        print(f"  [cached] {os.path.basename(op)}", flush=True)
        return op  # cached — skip the (large) source load

    print(f"  Slicing {os.path.basename(path)}"
          f"  (region={region_tag}, {start_year}-{end_year}"
          + (f", {int(depth_m)}m" if depth_m is not None else "") + ") ... loading", flush=True)
    D = np.load(path, allow_pickle=True)
    keys = D.files
    tl = D["TimeList"]
    yrs = np.array([getattr(t, "year", -1) for t in tl])
    tmask = (yrs >= start_year) & (yrs <= end_year)
    if not tmask.any():
        raise ValueError(f"No timesteps in {start_year}-{end_year} for {os.path.basename(path)}.")
    ll = D["LatLong"]
    n = ll.shape[0]
    lat = ll[:, 0]
    lon = ll[:, 1]
    smask = (lat >= lat_min) & (lat <= lat_max)
    if lon_min is not None:
        smask = smask & (lon >= lon_min) & (lon <= lon_max)
    has_depth = (len(_npz_member_shape(path, "Energy_pu")) == 3)
    di = None
    if has_depth:
        depths = np.atleast_1d(D["Depth_m"])
        if depth_m is None or depth_m not in depths:
            raise ValueError(f"Ocean-current depth {depth_m} m not in {os.path.basename(path)} "
                             f"(has {list(depths)}).")
        di = int(np.where(depths == depth_m)[0][0])
        if "ValidSites" in keys:
            smask = smask & D["ValidSites"][di]
    sidx = np.flatnonzero(smask)
    if sidx.size == 0:
        raise ValueError(f"0 sites for {os.path.basename(path)} in the selected region/depth.")
    out = {}
    for k in keys:
        a = D[k]
        if k == "TimeList":
            out[k] = a[tmask]
        elif k == "Depth_m":
            out[k] = np.float64(depth_m) if has_depth else a
        elif k == "Energy_pu":
            out[k] = (a[:, di, :] if has_depth else a)[tmask][:, sidx]
        elif k == "RawResource" and hasattr(a, "ndim") and a.ndim >= 2 and a.shape[0] == len(tl):
            out[k] = (a[:, di, :] if a.ndim == 3 else a)[tmask][:, sidx]
        elif has_depth and hasattr(a, "ndim") and a.ndim == 2 and a.shape[0] == len(depths) and a.shape[1] == n:
            out[k] = a[di][sidx]
        elif hasattr(a, "ndim") and a.ndim >= 1 and a.shape[0] == n:
            out[k] = a[sidx, ...]
        else:
            out[k] = a
        # Free the just-loaded source array before loading the next one. For the
        # big arrays (Energy_pu, RawResource) out[k] is a separate sliced copy, so
        # this releases the ~32 GB original immediately instead of holding it.
        del a
    D.close()
    np.savez(op, **out)
    print(f"    -> {out['Energy_pu'].shape[0]} steps x {out['Energy_pu'].shape[1]} sites"
          f"   saved {os.path.basename(op)}", flush=True)
    return op


def _slice_transmission_region(src_path, lat_min, lat_max, lon_min, lon_max, region_tag, out_dir):
    """Region-slice a whole-coast transmission file by lat (+ optional lon).
    Cached like _slice_design."""
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(src_path))[0].replace(" ", "")
    op = os.path.join(out_dir, f"{base}_{region_tag}.npz")
    if os.path.isfile(op):
        return op
    T = np.load(src_path, allow_pickle=True)["TransmissionLineParameters"].item()
    ll = np.asarray(T["TL_LatLong"], dtype=float)
    Nt = ll.shape[0]
    mask = (ll[:, 0] >= lat_min) & (ll[:, 0] <= lat_max)
    if lon_min is not None:
        mask = mask & (ll[:, 1] >= lon_min) & (ll[:, 1] <= lon_max)
    if int(mask.sum()) == 0:
        raise ValueError(f"No transmission landing sites for {os.path.basename(src_path)} in the selected region.")
    out = {k: (np.asarray(v)[mask] if isinstance(v, np.ndarray) and v.ndim >= 1 and v.shape[0] == Nt else v)
           for k, v in T.items()}
    np.savez(op, TransmissionLineParameters=np.array(out, dtype=object))
    return op


def _box_mask(latlong, box):
    """Boolean mask of sites whose (lat, lon) fall inside the box."""
    ll = np.asarray(latlong, dtype=float)
    lat, lon = ll[:, 0], ll[:, 1]
    return ((lat >= box["lat_min"]) & (lat <= box["lat_max"]) &
            (lon >= box["lon_min"]) & (lon <= box["lon_max"]))


def _filter_resource_npz_to_box(src_path, box, tag):
    """Copy a wind/wave/kite .npz keeping only sites inside the box.

    Every array whose shape contains the site dimension N is sliced along that
    axis; everything else (scalars, time list, etc.) is preserved as-is.
    Returns (out_path, n_sites). n_sites == 0 means nothing was in range.
    """
    D = np.load(src_path, allow_pickle=True)
    if "LatLong" not in D.files:
        return None, 0
    N = np.asarray(D["LatLong"]).shape[0]
    mask = _box_mask(D["LatLong"], box)
    n_in = int(mask.sum())
    if n_in == 0:
        return None, 0
    out = {}
    for k in D.files:
        a = D[k]
        arr = np.asarray(a)
        if arr.ndim >= 1 and N in arr.shape:
            sl = tuple(mask if dim == N else slice(None) for dim in arr.shape)
            out[k] = arr[sl]
        else:
            out[k] = a
    os.makedirs(BOX_TMP_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(src_path))[0]
    out_path = os.path.join(BOX_TMP_DIR, f"{base}__{tag}_box.npz")
    np.savez(out_path, **out)
    return out_path, n_in


def _filter_transmission_npzs_to_box(src_paths, box, tag):
    """Merge transmission landing sites from one or more state files, keeping
    only sites inside the box, into a single .npz the model can load.

    Transmission data lives in a dict under 'TransmissionLineParameters' with
    per-site arrays (length == number of landing points) keyed off TL_LatLong.
    Shared lookup tables (cable data, rated power) are taken from the first file.
    Returns (out_path, n_sites).
    """
    merged = None
    site_keys = None
    total = 0
    for sp in src_paths:
        T = np.load(sp, allow_pickle=True)["TransmissionLineParameters"].item()
        ll = np.asarray(T["TL_LatLong"], dtype=float)
        Nt = ll.shape[0]
        mask = _box_mask(ll, box)
        if int(mask.sum()) == 0:
            continue
        keys = [k for k, v in T.items()
                if isinstance(v, np.ndarray) and v.ndim >= 1 and v.shape[0] == Nt]
        if merged is None:
            merged = dict(T)
            for k in keys:
                merged[k] = np.asarray(T[k])[mask]
            site_keys = keys
        else:
            for k in site_keys:
                merged[k] = np.concatenate([merged[k], np.asarray(T[k])[mask]], axis=0)
        total += int(mask.sum())
    if merged is None or total == 0:
        return None, 0
    os.makedirs(BOX_TMP_DIR, exist_ok=True)
    out_path = os.path.join(BOX_TMP_DIR, f"transmission__{tag}_box.npz")
    np.savez(out_path, TransmissionLineParameters=np.array(merged, dtype=object))
    return out_path, total


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.route('/test', methods=['GET', 'POST'])
def test():
    return jsonify({'message': 'The server is running'})


def _available_wholecoast():
    """List whole-coast design files (region-independent). The region (state lat
    range or custom box) and year range are applied at run time by slicing these
    files, matching the notebook workflow."""
    result = {"wind": [], "wave": [], "kite": [], "coaxial": [], "transmission": []}

    # Wind: GenPU_{turbine}_EastCoast_2011_2020.npz
    for f in sorted(globmod.glob(os.path.join(TECH_OUTPUTS, "Wind", "GenPU_*_EastCoast_*.npz"))):
        core = _clean_core(f)
        name = core[len("GenPU_"):] if core.startswith("GenPU_") else core
        result["wind"].append({"name": name, "label": name.replace("_", " "), "path": f})

    # Wave: GenPU_{device}_EastCoast_2011_2020.npz
    for f in sorted(globmod.glob(os.path.join(TECH_OUTPUTS, "Wave", "GenPU_*_EastCoast_*.npz"))):
        core = _clean_core(f)
        name = core[len("GenPU_"):] if core.startswith("GenPU_") else core
        result["wave"].append({"name": name, "label": name.replace("_", " "), "path": f})

    # Kite / ocean current: kite_*_2011_2020.npz
    for f in sorted(globmod.glob(os.path.join(TECH_OUTPUTS, "Current", "kite_*.npz"))):
        core = _clean_core(f)
        _kw = re.search(r"(\d+)kW", core)
        _klabel = f"Kite {_kw.group(1)} kW" if _kw else core.replace("_", " ")
        result["kite"].append({"name": core, "label": _klabel, "path": f})

    # Coaxial / ocean current: coax_*_2011_2020.npz
    for f in sorted(globmod.glob(os.path.join(TECH_OUTPUTS, "Coaxial", "coax_*.npz"))):
        core = _clean_core(f)
        _ckw = re.search(r"(\d+)kW", core)
        _clabel = f"Coaxial {_ckw.group(1)} kW" if _ckw else core.replace("_", " ")
        result["coaxial"].append({"name": core, "label": _clabel, "path": f})

    # Transmission: Transmission_{cap}MW_East Coast.npz
    for f in sorted(globmod.glob(os.path.join(TECH_OUTPUTS, "Transmission", "Transmission_*MW_East Coast.npz"))):
        cap = os.path.basename(f).split("_")[1]  # e.g. '1200MW'
        result["transmission"].append({"name": cap, "label": cap.replace("MW", " MW"), "path": f})

    return result


@app.route('/availableData', methods=['POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def available_data():
    """List the whole-coast design files. They are region-independent; the app slices
    them to the selected state/box + year range at run time."""
    try:
        requestdata = request.get_json() or {}
        box = requestdata.get('box', None)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    result = _available_wholecoast()

    # For a custom box, also report which modeled states it overlaps (informational).
    if box:
        try:
            b = {k: float(box[k]) for k in ("lat_min", "lat_max", "lon_min", "lon_max")}
            result["states"] = [STATE_TRANSMISSION_NAMES.get(s, s)
                                for s in _states_in_lat_range(b["lat_min"], b["lat_max"])]
        except (KeyError, TypeError, ValueError):
            pass

    return jsonify(result)


@app.route('/resourceUpload', methods=['POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def resourceUpload():
    try:
        data = request.get_json()
        print(f"Received data: {data}")
    except Exception as e:
        print(f"JSON parse error: {str(e)}")

    try:
        from werkzeug.utils import secure_filename
        files = request.files.getlist('files')
        print(files)
        saved_files = []
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Detect technology from filename
                if "KitePower" in filename or "PowerTimeSeriesKite" in filename:
                    save_dir = os.path.join(TECH_OUTPUTS, 'Current')
                elif "Wind" in filename or "GenPU" in filename or "GenCost" in filename:
                    save_dir = os.path.join(TECH_OUTPUTS, 'Wind')
                elif "Wave" in filename or "HalfScale" in filename or "Pelamis" in filename or "RM3" in filename:
                    save_dir = os.path.join(TECH_OUTPUTS, 'Wave')
                elif "Transmission" in filename:
                    save_dir = os.path.join(TECH_OUTPUTS, 'Transmission')
                else:
                    save_dir = TECH_OUTPUTS
                os.makedirs(save_dir, exist_ok=True)
                print(f"Saving to {os.path.join(save_dir, filename)}")
                file.save(os.path.join(save_dir, filename))
                saved_files.append(filename)

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": f"Invalid request format: {str(e)}"}), 400

    return jsonify({'message': f'{len(saved_files)} file(s) uploaded successfully', 'files': saved_files}), 200


@app.route('/generateWindBinaries', methods=['GET', 'POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def generate_wind_binaries():
    """Generate wind tech outputs from raw wind speed data.
    Only needed if pre-computed GenPU files don't exist for the desired turbine/state.
    """
    try:
        data = request.get_json()
        print(f"Received data: {data}")
    except Exception as e:
        print(f"JSON parse error: {str(e)}")

    required_fields = ['WindTurbine']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    try:
        requestdata = request.get_json()
        WindTurbine = requestdata['WindTurbine']

        from WindTurbineTools_EastCoast import GetCostAndGenerationWindTurbine

        WindCostPath = os.path.join(INPUT_DATA, "Wind", "CostWindTurbines.xlsx")
        WindDataDir = os.path.join(INPUT_DATA, "Wind")

        WindSpeedHeightsAvailable = {
            100: "windspeed_100m",
            140: "windspeed_140m",
            160: "windspeed_160m",
        }

        # Optional: state filter applied after generation
        state_code = requestdata.get('state', None)
        state_display = STATE_DISPLAY_NAMES.get(state_code, "") if state_code else ""

        for tb in WindTurbine:
            TurbinePath = os.path.join(INPUT_DATA, "Wind", tb)
            WindDataFile = os.path.join(WindDataDir, "EastCoast_windspeed.npz")
            SavePath = os.path.join(TECH_OUTPUTS, "Wind", f"GenPU_{tb}{state_display}.npz")

            if not os.path.exists(SavePath):
                if not os.path.exists(WindDataFile):
                    return jsonify({"error": f"Raw wind data not found: {WindDataFile}"}), 404
                GetCostAndGenerationWindTurbine(
                    WindDataDir, WindCostPath, WindTurbine=tb,
                    WindDataFile=WindDataFile,
                    WindSpeedHeightsAvailable=WindSpeedHeightsAvailable,
                    TurbinePath=TurbinePath,
                    SavePath=SavePath,
                )
            else:
                print(f"{SavePath} already exists")

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": f"Invalid request format: {str(e)}"}), 400

    return jsonify({'message': 'The server executed this API call.'})


@app.route('/portfolioOptimization', methods=['POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def portfolioOptimization():
    """Run portfolio optimization using pre-computed East Coast Model files.

    Expects JSON with:
      wind:         list of absolute file paths to wind NPZ files
      wave:         list of absolute file paths to wave NPZ files
      kite:         list of absolute file paths to kite NPZ files
      transmission: list of absolute file paths to transmission NPZ files
      lcoe_max, lcoe_min, lcoe_step: LCOE range parameters
      max_system_radius: collection radius in km
      WindTurbinesPerSite, KiteTurbinesPerSite, WaveTurbinesPerSite: device counts
      max_wind, min_wind, max_kite, min_kite, max_wave, min_wave: design constraints
    """
    try:
        data = request.get_json()
        print(f"Received data: {data}")
    except Exception as e:
        print(f"JSON parse error: {str(e)}")

    required_fields = ['wind', 'wave', 'kite', 'transmission']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    try:
        requestdata = request.get_json()

        # ----- Region: custom box (lat + lon) or state (lat only) -----
        box = requestdata.get('box', None)
        state_code = requestdata.get('state', None)
        if box:
            try:
                b = {k: float(box[k]) for k in ("lat_min", "lat_max", "lon_min", "lon_max")}
            except (KeyError, TypeError, ValueError):
                return jsonify({"error": "Custom range is not valid: lat_min, lat_max, lon_min and lon_max must all be numbers."}), 400
            REGION_LAT_MIN, REGION_LAT_MAX = b["lat_min"], b["lat_max"]
            REGION_LON_MIN, REGION_LON_MAX = b["lon_min"], b["lon_max"]
            REGION_TAG = ("Box%g-%g" % (b["lat_min"], b["lat_max"])).replace(".", "p").replace("-", "m")
        elif state_code:
            rng = STATE_LAT_RANGES.get(state_code)
            if not rng:
                return jsonify({"error": f"Unknown state: {state_code}"}), 400
            REGION_LAT_MIN, REGION_LAT_MAX = rng[0], rng[1]
            REGION_LON_MIN, REGION_LON_MAX = None, None
            REGION_TAG = STATE_DISPLAY_NAMES.get(state_code, state_code)
        else:
            return jsonify({"error": "Select a state or a custom lat/long range."}), 400

        # ----- Year range (required — slices the whole-coast files) -----
        try:
            start_year = int(requestdata.get('start_year'))
            end_year = int(requestdata.get('end_year'))
        except (TypeError, ValueError):
            return jsonify({"error": "Start Year and End Year are required (whole numbers)."}), 400
        if start_year > end_year:
            return jsonify({"error": "Start Year must be less than or equal to End Year."}), 400

        # ----- Ocean-current depths (required if kite designs are selected) -----
        ocean_depths = requestdata.get('ocean_current_depths', []) or []
        if not isinstance(ocean_depths, list):
            ocean_depths = [ocean_depths]
        try:
            ocean_depths = [int(d) for d in ocean_depths]
        except (TypeError, ValueError):
            return jsonify({"error": "Ocean-current depths must be whole numbers."}), 400

        # Slice folder: one per region + year range (cached across runs so the big
        # whole-coast files are only loaded the first time this region/years is used).
        # Results folder is named by exactly which designs are checked in the GUI,
        # so the same region/years with a different tech selection does NOT overwrite:
        #   Portfolios/{REGION}_{start}_{end}_{design1+design2+...}/
        # Ocean-current depth(s) are appended when kite/coaxial are selected, since
        # those runs differ by depth and would otherwise still collide.
        _selected_designs = (requestdata.get('wind', []) + requestdata.get('wave', [])
                             + requestdata.get('kite', []) + requestdata.get('coaxial', []))
        _design_tag = "+".join(_design_short(p) for p in _selected_designs) or "none"
        if (requestdata.get('kite') or requestdata.get('coaxial')) and ocean_depths:
            _design_tag += "_oc" + "-".join(str(d) for d in ocean_depths) + "m"
        # Environmental / shipping exclusions (optional). Enabled ones are encoded
        # in the run folder so exclusion scenarios do not overwrite non-exclusion runs.
        _env = requestdata.get('environmental', {}) or {}
        _env_code = "".join(c for k, c in [('hapc', 'H'), ('prohibited', 'P'),
                                           ('restricted', 'R'), ('shipping', 'S')] if _env.get(k))
        if _env_code:
            _design_tag += "_env" + _env_code
        RUN_ID = f"{REGION_TAG}_{start_year}_{end_year}_{_design_tag}"
        RUN_DIR = os.path.join(PORTFOLIOS_DIR, RUN_ID)
        # Slice cache is shared per region+years only (independent of tech selection),
        # so the big whole-coast files are sliced once and reused across tech combos.
        SLICE_DIR = os.path.join(PORTFOLIOS_DIR, f"{REGION_TAG}_{start_year}_{end_year}", "inputs")
        print(f"=== Preparing inputs: slicing whole-coast designs to region '{REGION_TAG}', "
              f"years {start_year}-{end_year}. First run for a region loads the full files "
              f"(can take several minutes each); later runs reuse the cache. ===", flush=True)

        # Slice each selected design to the region/depth. A design with no viable
        # sites here (e.g. an ocean-current design whose flow-speed bin does not
        # occur in this box/depth) is SKIPPED with a warning rather than failing
        # the whole run -- non-viable designs simply drop out of the portfolio.
        _slice_warnings = []
        def _slice_list(srcs, depths=None):
            out = []
            for src in srcs:
                combos = [(src, d) for d in depths] if depths else [(src, None)]
                for _src, _d in combos:
                    if not os.path.isfile(_src):
                        _slice_warnings.append(f"File not found (skipped): {_src}")
                        continue
                    try:
                        if _d is not None:
                            out.append(_slice_design(_src, REGION_LAT_MIN, REGION_LAT_MAX,
                                                     REGION_LON_MIN, REGION_LON_MAX,
                                                     start_year, end_year, REGION_TAG, SLICE_DIR, depth_m=_d))
                        else:
                            out.append(_slice_design(_src, REGION_LAT_MIN, REGION_LAT_MAX,
                                                     REGION_LON_MIN, REGION_LON_MAX,
                                                     start_year, end_year, REGION_TAG, SLICE_DIR))
                    except ValueError as _e:
                        _tag = f" @ {_d}m" if _d is not None else ""
                        _slice_warnings.append(f"Skipped {os.path.basename(_src)}{_tag}: {_e}")
            return out

        PathWindDesigns = _slice_list(requestdata.get('wind', []))
        PathWaveDesigns = _slice_list(requestdata.get('wave', []))

        kite_srcs = requestdata.get('kite', [])
        if kite_srcs and not ocean_depths:
            return jsonify({"error": "Select at least one ocean-current depth for the kite designs."}), 400
        PathKiteDesigns = _slice_list(kite_srcs, depths=ocean_depths)

        coax_srcs = requestdata.get('coaxial', [])
        if coax_srcs and not ocean_depths:
            return jsonify({"error": "Select at least one ocean-current depth for the coaxial designs."}), 400
        PathCoaxialDesigns = _slice_list(coax_srcs, depths=ocean_depths)

        for _w in _slice_warnings:
            print("  [skip] " + _w, flush=True)

        if not (PathWindDesigns or PathWaveDesigns or PathKiteDesigns or PathCoaxialDesigns):
            return jsonify({"error": "No viable designs in this region/depth after filtering. "
                            + " | ".join(_slice_warnings)}), 400

        # Transmission: region-slice (lat + optional lon), no time axis
        PathTransmissionDesign = []
        for src in requestdata.get('transmission', []):
            if not os.path.isfile(src):
                return jsonify({"error": f"File not found: {src}"}), 404
            try:
                PathTransmissionDesign.append(
                    _slice_transmission_region(src, REGION_LAT_MIN, REGION_LAT_MAX,
                                               REGION_LON_MIN, REGION_LON_MAX, REGION_TAG, SLICE_DIR))
            except ValueError as _e:
                return jsonify({"error": str(_e)}), 400

        # A tech with no viable designs must not carry a min/max requirement,
        # or the model would be forced to site a device that cannot exist here.
        if not PathWindDesigns:    requestdata['max_wind'] = 0;    requestdata['min_wind'] = 0
        if not PathWaveDesigns:    requestdata['max_wave'] = 0;    requestdata['min_wave'] = 0
        if not PathKiteDesigns:    requestdata['max_kite'] = 0;    requestdata['min_kite'] = 0
        if not PathCoaxialDesigns: requestdata['max_coaxial'] = 0; requestdata['min_coaxial'] = 0

        max_wind = requestdata.get('max_wind', 1)
        min_wind = requestdata.get('min_wind', 0)
        max_kite = requestdata.get('max_kite', 1)
        min_kite = requestdata.get('min_kite', 0)
        max_wave = requestdata.get('max_wave', 1)
        min_wave = requestdata.get('min_wave', 0)
        max_coaxial = requestdata.get('max_coaxial', 1)
        min_coaxial = requestdata.get('min_coaxial', 0)

        lcoe_max = requestdata.get('lcoe_max', 200)
        lcoe_min = requestdata.get('lcoe_min', 40)
        lcoe_step = requestdata.get('lcoe_step', 2)
        max_system_radius = requestdata.get('max_system_radius', 30)
        WindTurbinesPerSite = requestdata.get('WindTurbinesPerSite', 4)
        KiteTurbinesPerSite = requestdata.get('KiteTurbinesPerSite', 390)
        WaveTurbinesPerSite = requestdata.get('WaveTurbinesPerSite', 300)
        CoaxialTurbinesPerSite = requestdata.get('CoaxialTurbinesPerSite', 390)

        LCOE_RANGE = range(lcoe_max, lcoe_min, -1 * lcoe_step)
        Max_CollectionRadious = max_system_radius
        MaxDesignsWind = max_wind
        MaxDesingsKite = max_kite
        MinNumWindTurb = min_wind
        MinNumKiteTrub = min_kite
        MaxDesingsWave = max_wave
        MinNumWaveTurb = min_wave
        MaxDesignsCoaxial = max_coaxial
        MinNumCoaxialTurb = min_coaxial

        print("Wind paths:", PathWindDesigns)
        print("Kite paths:", PathKiteDesigns)
        print("Wave paths:", PathWaveDesigns)
        print("Transmission paths:", PathTransmissionDesign)

        # Match the notebook's naming convention exactly:
        #   TechCaseName         = "_".join of each tech's filename (no extension)
        #   TransmissionCaseName = transmission filename (no extension)
        #   Folder/Save base     = TechCaseName + "_" + TransmissionCaseName
        def _extract_name(path):
            # Strip directory and ".npz" extension, matching notebook logic
            return os.path.splitext(os.path.basename(path))[0]

        tech_labels = [_extract_name(p) for p in PathWindDesigns + PathWaveDesigns + PathKiteDesigns + PathCoaxialDesigns]
        if not tech_labels:
            return jsonify({"error": "Select at least one resource (wind, wave, or kite)."}), 400
        TechCaseName = "_".join(tech_labels)

        # Per-tech cost adjustment (% of baseline; 100 = no change). Set the model's
        # module-level *CostScaling globals (e.g. 70 -> 0.70 = 70% of baseline cost).
        # All five are reset every request so values never leak between runs.
        _cost_adjust = requestdata.get('cost_adjust', {}) or {}
        def _scale_frac(key):
            try:
                v = float(_cost_adjust.get(key, 100))
            except (TypeError, ValueError):
                v = 100.0
            if v <= 0:
                v = 100.0
            return v / 100.0
        _model.windCostScaling    = _scale_frac('wind')
        _model.waveCostScaling    = _scale_frac('wave')
        _model.kiteCostScaling    = _scale_frac('kite')
        _model.coaxialCostScaling = _scale_frac('coaxial')
        _model.tidalCostScaling   = _scale_frac('tidal')
        # The model appends this same suffix to its output folders when any scaling
        # != 1.0; replicate it so the returned run id points to the right folder.
        _scaling_pairs = [("wind", _model.windCostScaling), ("wave", _model.waveCostScaling),
                          ("kite", _model.kiteCostScaling), ("coax", _model.coaxialCostScaling),
                          ("tidal", _model.tidalCostScaling)]
        scaling_tag = "".join("_%s%g" % (nm, val) for nm, val in _scaling_pairs if val != 1.0)

        # Resolve exclusion file paths (None when that exclusion is not enabled).
        _env_files = {
            'hapc':       os.path.join(ENVIRONMENT_DIR, "HAPC_hard_bottom_habitat.txt"),
            'prohibited': os.path.join(ENVIRONMENT_DIR, "prohibitedmpas.txt"),
            'restricted': os.path.join(ENVIRONMENT_DIR, "restricteddfmpas.txt"),
            'shipping':   os.path.join(ENVIRONMENT_DIR, "shipping_no_development.txt"),
        }
        def _env_path(key):
            return _env_files[key] if _env.get(key) else None
        HAPCExclusionPath          = _env_path('hapc')
        ProhibitedMPAExclusionPath = _env_path('prohibited')
        RestrictedMPAExclusionPath = _env_path('restricted')
        ShippingExclusionPath      = _env_path('shipping')

        SavePaths = []
        PortfolioIds = []

        for PathTransmissionDesign_i in PathTransmissionDesign:
            TransmissionCaseName = _extract_name(PathTransmissionDesign_i)

            # Notebook layout: per-LCOE outputs + summary live inside the run folder.
            PerLCOE_OutputFolder = os.path.join(RUN_DIR, TransmissionCaseName)
            SavePath = os.path.join(RUN_DIR, TransmissionCaseName + "_summary")
            ReadMe = f"Techs: {TechCaseName} | Transmission: {TransmissionCaseName}"

            SavePaths.append(SavePath + scaling_tag + '.npz')
            PortfolioIds.append(f"{RUN_ID}/{TransmissionCaseName}{scaling_tag}")

            print(f"Running: {TechCaseName}")
            print(f"Transmission: {TransmissionCaseName}")
            print(f"Save base: {SavePath}")

            # Always run (no short-circuit skip) - matches notebook behavior
            # NOTE: the East Coast model adds Coaxial and Tidal technologies.
            # The web app does not expose those yet, so they are passed as empty
            # (no design paths, zero min/max constraints) to preserve wind/wave/kite behavior.
            PathTidalDesigns = []
            SolvePortOpt_MaxGen_LCOE_Iterator(
                PathWindDesigns, PathWaveDesigns, PathKiteDesigns,
                PathCoaxialDesigns, PathTidalDesigns,
                PathTransmissionDesign_i, LCOE_RANGE,
                Max_CollectionRadious, MaxDesignsWind, MaxDesingsWave,
                MaxDesingsKite, MaxDesignsCoaxial, 0,
                MinNumWindTurb, MinNumWaveTurb, MinNumKiteTrub, MinNumCoaxialTurb, 0,
                ReadMe,
                SavePath=SavePath,
                PerLCOE_OutputFolder=PerLCOE_OutputFolder,
                WindTurbinesPerSite=WindTurbinesPerSite,
                KiteTurbinesPerSite=KiteTurbinesPerSite,
                WaveTurbinesPerSite=WaveTurbinesPerSite,
                CoaxialTurbinesPerSite=CoaxialTurbinesPerSite,
                HAPCExclusionPath=HAPCExclusionPath,
                ProhibitedMPAExclusionPath=ProhibitedMPAExclusionPath,
                RestrictedMPAExclusionPath=RestrictedMPAExclusionPath,
                ShippingExclusionPath=ShippingExclusionPath,
            )
            print("Done with " + SavePath)

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": f"Invalid request format: {str(e)}"}), 400

    return jsonify({'message': 'The server executed this API call.', 'save_path': SavePaths, 'portfolio_ids': PortfolioIds})


@app.route('/portfolioPlots', methods=['POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def portfolioPlots():
    try:
        data = request.get_json()
        print(f"Received data: {data}")
    except Exception as e:
        print(f"JSON parse error: {str(e)}")

    required_fields = ['portfolio']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    try:
        requestdata = request.get_json()
        portfolio_paths = requestdata['portfolio']

        SolutionPaths = []
        for pp in portfolio_paths:
            # Handle both absolute paths and relative paths
            if os.path.isabs(pp) and os.path.exists(pp):
                SolutionPaths.append(pp)
            else:
                # Try relative to PORTFOLIOS_DIR
                candidate = os.path.join(PORTFOLIOS_DIR, os.path.basename(pp))
                if os.path.exists(candidate):
                    SolutionPaths.append(candidate)
                else:
                    SolutionPaths.append(pp)

        resource_type = {
            '8MW_2020_Vestas': '8MW Vestas 2020',
            '12MW_2030': '12MW 2030',
            '15MW_2030': '15MW 2030',
            '18MW_2030': '18MW 2030',
            'Design0': 'Kite Design 0',
            'Design1': 'Kite Design 1',
            'Design2': 'Kite Design 2',
            'Design3': 'Kite Design 3',
            'HalfScale': 'HalfScale WEC',
            'Pelamis': 'Pelamis WEC',
            'RM3': 'RM3 WEC',
        }

        resource_names = ""
        combined_path = " ".join(SolutionPaths)
        for key, val in resource_type.items():
            if key in combined_path:
                resource_names += val + '\n'

        Legend = [resource_names if resource_names else "Portfolio"]

        linestyle = ['-', '-', '--', '-.', '-', '--', '-.', '-', '--', '-.']
        ColorList = ['tab:orange', 'k', 'k', 'k', "b", "b", "b", "r", "r", "r"]
        Marker = [None] * len(SolutionPaths)

        SavePath = os.path.join(PLOTS_DIR, "UI.png")

        try:
            os.remove(SavePath)
        except Exception:
            print("No existing plot to remove")

        PlotEfficientFrontier(
            SolutionPaths, Legend, linestyle=linestyle,
            ColorList=ColorList, Marker=Marker, Title=None, SavePath=SavePath,
        )

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": f"Invalid request format: {str(e)}"}), 400

    if os.path.exists(SavePath):
        return send_file(SavePath, mimetype='image/png', as_attachment=False)
    else:
        return jsonify({"error": f"Plot not found at {SavePath}"}), 404


# ---------------------------------------------------------------------------
# List available portfolio runs
# ---------------------------------------------------------------------------

@app.route('/portfolioRuns', methods=['GET'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def list_portfolio_runs():
    """Return every completed portfolio run (any folder containing a Summary.csv),
    with metadata. Handles both nested runs (RUN_ID/TransmissionCase/) and older
    flat runs. Newest first."""
    runs = []
    if os.path.isdir(PORTFOLIOS_DIR):
        for dirpath, dirnames, filenames in os.walk(PORTFOLIOS_DIR):
            if "Summary.csv" in filenames:
                rel = os.path.relpath(dirpath, PORTFOLIOS_DIR).replace(os.sep, "/")
                try:
                    mtime = os.path.getmtime(os.path.join(dirpath, "Summary.csv"))
                except OSError:
                    mtime = 0
                runs.append({
                    "id": rel,
                    "name": rel,
                    "has_frontier": "Plot_EfficientFrontier.png" in filenames,
                    "has_stacked_costs": "Plot_StackedCosts.png" in filenames,
                    "mtime": mtime,
                })
                # No need to descend into a run's LCOE_* subfolders.
                dirnames[:] = [d for d in dirnames if not d.startswith("LCOE_")]
    runs.sort(key=lambda r: r["mtime"], reverse=True)
    return jsonify({"runs": runs})


# ---------------------------------------------------------------------------
# Per-LCOE plot endpoints
# ---------------------------------------------------------------------------

@app.route('/portfolioResults/<path:portfolio_id>/plots', methods=['GET'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def list_portfolio_plots(portfolio_id):
    base_folder = os.path.join(PORTFOLIOS_DIR, portfolio_id)
    if not os.path.isdir(base_folder):
        return jsonify({"error": "Portfolio output folder not found", "path": base_folder}), 404

    result = {"run_level": [], "per_lcoe": {}}
    for fname in sorted(os.listdir(base_folder)):
        fpath = os.path.join(base_folder, fname)
        if os.path.isfile(fpath) and (fname.endswith('.png') or fname.endswith('.csv')):
            result["run_level"].append(fname)
        elif os.path.isdir(fpath) and fname.startswith("LCOE_"):
            lcoe_files = [
                f for f in sorted(os.listdir(fpath))
                if f.endswith('.png') or f.endswith('.npz')
            ]
            result["per_lcoe"][fname] = lcoe_files

    return jsonify(result)


PLOT_TYPE_MAP = {
    "totalGeneration": "Plot_TotalGeneration.png",
    "stackedGeneration": "Plot_StackedGenByTech.png",
    "curtailment": "Plot_Curtailment.png",
    "deploymentMap": "Plot_DeploymentMap.png",
}


@app.route('/portfolioResults/<path:portfolio_id>/lcoe/<int:lcoe_target>/<plot_type>', methods=['GET'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def get_lcoe_plot(portfolio_id, lcoe_target, plot_type):
    if plot_type not in PLOT_TYPE_MAP:
        return jsonify({"error": f"Unknown plot type: {plot_type}", "valid": list(PLOT_TYPE_MAP.keys())}), 400
    filename = PLOT_TYPE_MAP[plot_type]
    plot_path = os.path.join(PORTFOLIOS_DIR, portfolio_id, f"LCOE_{lcoe_target}", filename)
    if os.path.exists(plot_path):
        return send_file(plot_path, mimetype='image/png', as_attachment=False)
    else:
        return jsonify({"error": f"Plot not found at {plot_path}"}), 404


@app.route('/portfolioResults/<path:portfolio_id>/summary', methods=['GET'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def get_portfolio_summary(portfolio_id):
    csv_path = os.path.join(PORTFOLIOS_DIR, portfolio_id, "Summary.csv")
    if os.path.exists(csv_path):
        return send_file(csv_path, mimetype='text/csv', as_attachment=True)
    else:
        return jsonify({"error": f"Summary not found at {csv_path}"}), 404


@app.route('/portfolioResults/<path:portfolio_id>/frontierData', methods=['GET'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def get_frontier_data(portfolio_id):
    """Return a run's Summary.csv as JSON points for the efficient-frontier overlay.
    X = Total_MW_Avg (avg net generation), Y = LCOE_Target ($/MWh), plus per-tech MW."""
    csv_path = os.path.join(PORTFOLIOS_DIR, portfolio_id, "Summary.csv")
    if not os.path.exists(csv_path):
        return jsonify({"error": f"Summary not found at {csv_path}"}), 404

    def _num(row, key):
        for col in row:
            if key in col:
                try:
                    return float(row[col])
                except (TypeError, ValueError):
                    return None
        return None

    points = []
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            points.append({
                "lcoe_target": _num(row, "LCOE_Target"),
                "lcoe_achieved": _num(row, "LCOE_Achieved"),
                "total_mw": _num(row, "Total_MW_Avg"),
                "wind_mw": _num(row, "Wind_MW_Avg"),
                "wave_mw": _num(row, "Wave_MW_Avg"),
                "kite_mw": _num(row, "Kite_MW_Avg"),
                "coaxial_mw": _num(row, "Coaxial_MW_Avg"),
                "tidal_mw": _num(row, "Tidal_MW_Avg"),
                "cost_wind": _num(row, "Cost_Wind"),
                "cost_wave": _num(row, "Cost_Wave"),
                "cost_kite": _num(row, "Cost_Kite"),
                "cost_coaxial": _num(row, "Cost_Coaxial"),
                "cost_tidal": _num(row, "Cost_Tidal"),
                "cost_transmission": _num(row, "Cost_Transmission"),
                "total_cost": _num(row, "Total_Cost"),
            })
    return jsonify({"id": portfolio_id, "points": points})


@app.route('/portfolioResults/<path:portfolio_id>/efficientFrontier', methods=['GET'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def get_efficient_frontier(portfolio_id):
    plot_path = os.path.join(PORTFOLIOS_DIR, portfolio_id, "Plot_EfficientFrontier.png")
    if os.path.exists(plot_path):
        return send_file(plot_path, mimetype='image/png', as_attachment=False)
    else:
        return jsonify({"error": f"Plot not found at {plot_path}"}), 404


@app.route('/portfolioResults/<path:portfolio_id>/stackedCosts', methods=['GET'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def get_stacked_costs(portfolio_id):
    plot_path = os.path.join(PORTFOLIOS_DIR, portfolio_id, "Plot_StackedCosts.png")
    if os.path.exists(plot_path):
        return send_file(plot_path, mimetype='image/png', as_attachment=False)
    else:
        return jsonify({"error": f"Plot not found at {plot_path}"}), 404


if __name__ == '__main__':
    app.run('0.0.0.0', 4000, debug=True)
