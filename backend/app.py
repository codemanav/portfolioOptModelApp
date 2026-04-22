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
from pathlib import Path
import traceback

from Port_Opt_MaxGeneration_EastCoast import SolvePortOpt_MaxGen_LCOE_Iterator
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

os.makedirs(PORTFOLIOS_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)
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

# Wind files have inconsistent naming; we try multiple patterns
def _find_wind_file(turbine_name, state_display):
    """Find wind NPZ for a given turbine and state, handling naming inconsistencies."""
    wind_dir = os.path.join(TECH_OUTPUTS, "Wind")
    # Try several naming patterns observed in the East Coast Model
    candidates = [
        os.path.join(wind_dir, f"GenPU_{turbine_name}{state_display}.npz"),         # GenPU_ATB_18MW_2030Virginia.npz
        os.path.join(wind_dir, f"GenPU_{turbine_name}_{state_display}.npz"),        # GenPU_ATB_18MW_2030_Florida.npz
        os.path.join(wind_dir, f"GenPU_{turbine_name}{state_display.replace('_','')}.npz"),  # GenPU_...NewJersey
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _find_wave_file(device_name, state_display):
    """Find wave NPZ for a given device and state."""
    candidates = [
        os.path.join(TECH_OUTPUTS, "Wave", "ByState_Uniform", f"{state_display}_{device_name}.npz"),
        os.path.join(TECH_OUTPUTS, "Wave", "ByState", f"{state_display}_{device_name}.npz"),
        os.path.join(TECH_OUTPUTS, "Wave", f"{state_display}_{device_name}.npz"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


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
# API Endpoints
# ---------------------------------------------------------------------------

@app.route('/test', methods=['GET', 'POST'])
def test():
    return jsonify({'message': 'The server is running'})


@app.route('/availableData', methods=['POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def available_data():
    """Return which designs are available for a given state."""
    try:
        requestdata = request.get_json()
        state_code = requestdata.get('state', '')
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    state_display = STATE_DISPLAY_NAMES.get(state_code, "")
    state_trans   = STATE_TRANSMISSION_NAMES.get(state_code, "")

    result = {"wind": [], "wave": [], "kite": [], "transmission": []}

    # --- Wind: scan for GenPU_* files matching this state ---
    wind_dir = os.path.join(TECH_OUTPUTS, "Wind")
    if os.path.isdir(wind_dir):
        turbine_names = ["ATB_8MW_2020_Vestas", "ATB_12MW_2030", "ATB_15MW_2030", "ATB_18MW_2030"]
        for tn in turbine_names:
            found = _find_wind_file(tn, state_display)
            if found:
                result["wind"].append({
                    "name": tn,
                    "label": tn.replace("ATB_", "").replace("_", " "),
                    "path": found
                })

    # --- Wave: scan ByState / ByState_Uniform ---
    wave_devices = ["HalfScale_63.62", "Pelamis", "RM3"]
    for wd in wave_devices:
        found = _find_wave_file(wd, state_display)
        if found:
            result["wave"].append({
                "name": wd,
                "label": wd.replace("_", " "),
                "path": found
            })

    # --- Kite/Current: scan for KitePower_Design* ---
    for design_id in range(10):
        found = _find_kite_file(design_id, state_display)
        if found:
            # Try to read rated power for label
            try:
                d = np.load(found, allow_pickle=True)
                rp = float(d['RatedPower'])
                label = f"Design {design_id} ({rp:.2f} MW)"
            except Exception:
                label = f"Design {design_id}"
            result["kite"].append({
                "name": f"Design{design_id}",
                "design_id": design_id,
                "label": label,
                "path": found
            })

    # --- Transmission ---
    for cap in [100, 300, 600, 1000, 1200]:
        found = _find_transmission_file(cap, state_code)
        if found:
            label = f"{cap} MW" if cap < 1000 else f"{cap/1000:.1f} GW"
            result["transmission"].append({
                "name": f"{cap}MW",
                "capacity_mw": cap,
                "label": label,
                "path": found
            })

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

        # File paths are now absolute paths sent by the frontend
        PathWindDesigns = requestdata['wind']
        PathKiteDesigns = requestdata['kite']
        PathWaveDesigns = requestdata['wave']
        PathTransmissionDesign = requestdata['transmission']

        # Validate all paths exist
        all_paths = PathWindDesigns + PathKiteDesigns + PathWaveDesigns + PathTransmissionDesign
        for p in all_paths:
            if not os.path.isfile(p):
                return jsonify({"error": f"File not found: {p}"}), 404

        max_wind = requestdata.get('max_wind', 1)
        min_wind = requestdata.get('min_wind', 0)
        max_kite = requestdata.get('max_kite', 1)
        min_kite = requestdata.get('min_kite', 0)
        max_wave = requestdata.get('max_wave', 1)
        min_wave = requestdata.get('min_wave', 0)

        lcoe_max = requestdata.get('lcoe_max', 200)
        lcoe_min = requestdata.get('lcoe_min', 40)
        lcoe_step = requestdata.get('lcoe_step', 2)
        max_system_radius = requestdata.get('max_system_radius', 30)
        WindTurbinesPerSite = requestdata.get('WindTurbinesPerSite', 4)
        KiteTurbinesPerSite = requestdata.get('KiteTurbinesPerSite', 390)
        WaveTurbinesPerSite = requestdata.get('WaveTurbinesPerSite', 300)

        LCOE_RANGE = range(lcoe_max, lcoe_min, -1 * lcoe_step)
        Max_CollectionRadious = max_system_radius
        MaxDesignsWind = max_wind
        MaxDesingsKite = max_kite
        MinNumWindTurb = min_wind
        MinNumKiteTrub = min_kite
        MaxDesingsWave = max_wave
        MinNumWaveTurb = min_wave

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

        tech_labels = []
        if len(PathWindDesigns) > 0:
            tech_labels += [_extract_name(p) for p in PathWindDesigns]
        if len(PathWaveDesigns) > 0:
            tech_labels += [_extract_name(p) for p in PathWaveDesigns]
        if len(PathKiteDesigns) > 0:
            tech_labels += [_extract_name(p) for p in PathKiteDesigns]

        if len(tech_labels) == 0:
            return jsonify({"error": "At least one technology must have design paths!"}), 400

        TechCaseName = "_".join(tech_labels)

        SavePaths = []

        for PathTransmissionDesign_i in PathTransmissionDesign:
            TransmissionCaseName = _extract_name(PathTransmissionDesign_i)

            # Both SavePath and PerLCOE_OutputFolder use the SAME base path (matches notebook)
            base_name = TechCaseName + "_" + TransmissionCaseName
            SavePath = os.path.join(PORTFOLIOS_DIR, base_name)
            PerLCOE_OutputFolder = SavePath
            ReadMe = f"Techs: {TechCaseName} | Transmission: {TransmissionCaseName}"

            SavePaths.append(SavePath + '.npz')

            print(f"Running: {TechCaseName}")
            print(f"Transmission: {TransmissionCaseName}")
            print(f"Save base: {SavePath}")

            # Always run (no short-circuit skip) - matches notebook behavior
            SolvePortOpt_MaxGen_LCOE_Iterator(
                PathWindDesigns, PathWaveDesigns, PathKiteDesigns,
                PathTransmissionDesign_i, LCOE_RANGE,
                Max_CollectionRadious, MaxDesignsWind, MaxDesingsWave,
                MaxDesingsKite, MinNumWindTurb, MinNumWaveTurb,
                MinNumKiteTrub, ReadMe,
                SavePath=SavePath,
                PerLCOE_OutputFolder=PerLCOE_OutputFolder,
                WindTurbinesPerSite=WindTurbinesPerSite,
                KiteTurbinesPerSite=KiteTurbinesPerSite,
                WaveTurbinesPerSite=WaveTurbinesPerSite,
            )
            print("Done with " + SavePath)

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": f"Invalid request format: {str(e)}"}), 400

    return jsonify({'message': 'The server executed this API call.', 'save_path': SavePaths})


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
    """Return list of portfolio run IDs that have result folders."""
    runs = []
    if os.path.isdir(PORTFOLIOS_DIR):
        for name in sorted(os.listdir(PORTFOLIOS_DIR)):
            folder_path = os.path.join(PORTFOLIOS_DIR, name)
            if os.path.isdir(folder_path) and name != '_plots':
                runs.append(name)
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
