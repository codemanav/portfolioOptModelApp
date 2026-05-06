from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pandas as pd
from flask import jsonify, request

try:
    from power_surface_generation import (
        generate_model_from_dataframe,
        save_generated_model,
    )
except ImportError:
    from .power_surface_generation import (
        generate_model_from_dataframe,
        save_generated_model,
    )


OUTPUT_DIR = Path("generated_surfaces")


def register_upload_routes(flask_app, output_dir: str | Path | None = None) -> None:
    """Register power-surface upload endpoints on the existing Flask app."""
    target_output_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    @flask_app.route("/upload/health", methods=["GET"])
    def upload_health():
        return jsonify({"status": "ok"})

    @flask_app.route("/upload/power-surface", methods=["POST"])
    def upload_power_surface():
        uploaded_file = request.files.get("file")
        if uploaded_file is None:
            return jsonify({"error": "Missing multipart file field 'file'."}), 400
        if not uploaded_file.filename or not uploaded_file.filename.lower().endswith(".csv"):
            return jsonify({"error": "Please upload a CSV file."}), 400

        technology = request.args.get("technology")
        if not technology:
            return jsonify({"error": "Missing required query parameter: technology"}), 400

        x_column = request.args.get("x_column", "Depth")
        y_column = request.args.get("y_column", "Velocity")
        power_column = request.args.get("power_column", "Power")
        try:
            grid_points = int(request.args.get("grid_points", 50))
        except ValueError:
            return jsonify({"error": "grid_points must be an integer."}), 400
        if grid_points < 5 or grid_points > 200:
            return jsonify({"error": "grid_points must be between 5 and 200."}), 400

        try:
            dataframe = pd.read_csv(uploaded_file.stream)
            result = generate_model_from_dataframe(
                df=dataframe,
                technology=technology,
                x_column=x_column,
                y_column=y_column,
                power_column=power_column,
                grid_points=grid_points,
            )
            output_name = f"{Path(uploaded_file.filename).stem}_{result.technology}_{uuid4().hex[:8]}"
            saved_paths = save_generated_model(result, target_output_dir, output_name)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except Exception as error:
            return jsonify({"error": f"Power surface generation failed: {error}"}), 500

        return jsonify(
            {
                "message": "Power surface generated successfully.",
                "input_file": uploaded_file.filename,
                "technology": result.technology,
                "model_kind": result.model_kind,
                "output_files": saved_paths,
                "shape": {
                    "x": list(result.x.shape),
                    "y": list(result.y.shape) if result.y is not None else None,
                    "power": list(result.power.shape),
                },
            }
        )
