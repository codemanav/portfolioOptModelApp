from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.interpolate import griddata


@dataclass
class TechnologyGenerationResult:
    technology: str
    model_kind: str
    x: np.ndarray
    y: np.ndarray | None
    power: np.ndarray


def _validate_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")


SURFACE_TECHNOLOGIES = {"kite", "ocean_current", "wave", "polamis", "rm3"}
CURVE_TECHNOLOGIES = {"coaxial", "wind"}
SUPPORTED_TECHNOLOGIES = SURFACE_TECHNOLOGIES | CURVE_TECHNOLOGIES


def _normalize_technology(technology: str) -> str:
    normalized = technology.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"current", "oceancurrent"}:
        normalized = "ocean_current"
    if normalized not in SUPPORTED_TECHNOLOGIES:
        supported = ", ".join(sorted(SUPPORTED_TECHNOLOGIES))
        raise ValueError(f"Unsupported technology '{technology}'. Supported: {supported}")
    return normalized


def _generate_surface_model(
    df: pd.DataFrame,
    x_column: str,
    y_column: str,
    power_column: str = "Power",
    grid_points: int = 50,
) -> TechnologyGenerationResult:
    _validate_columns(df, [x_column, y_column, power_column])
    if grid_points < 5:
        raise ValueError("grid_points must be >= 5")

    clean_df = df[[x_column, y_column, power_column]].dropna()
    if clean_df.empty:
        raise ValueError("No valid rows after dropping missing values")

    x_values = clean_df[x_column].to_numpy(dtype=float)
    y_values = clean_df[y_column].to_numpy(dtype=float)
    powers = clean_df[power_column].to_numpy(dtype=float)

    x_grid = np.linspace(x_values.min(), x_values.max(), grid_points)
    y_grid = np.linspace(y_values.min(), y_values.max(), grid_points)
    grid_x, grid_y = np.meshgrid(x_grid, y_grid, indexing="xy")

    points = np.column_stack((x_values, y_values))
    grid_power_linear = griddata(points, powers, (grid_x, grid_y), method="linear")
    grid_power_nearest = griddata(points, powers, (grid_x, grid_y), method="nearest")
    grid_power = np.where(np.isnan(grid_power_linear), grid_power_nearest, grid_power_linear)

    return TechnologyGenerationResult(
        technology="",
        model_kind="surface",
        x=grid_x,
        y=grid_y,
        power=grid_power,
    )


def _generate_curve_model(
    df: pd.DataFrame,
    x_column: str,
    power_column: str = "Power",
    grid_points: int = 50,
) -> TechnologyGenerationResult:
    _validate_columns(df, [x_column, power_column])
    if grid_points < 5:
        raise ValueError("grid_points must be >= 5")

    clean_df = df[[x_column, power_column]].dropna()
    if clean_df.empty:
        raise ValueError("No valid rows after dropping missing values")

    grouped = clean_df.groupby(x_column, as_index=False)[power_column].max()
    grouped = grouped.sort_values(x_column)
    x_values = grouped[x_column].to_numpy(dtype=float)
    power_values = grouped[power_column].to_numpy(dtype=float)
    if len(x_values) < 2:
        raise ValueError("At least two unique x-axis values are required for a curve model")

    x_grid = np.linspace(x_values.min(), x_values.max(), grid_points)
    power_grid = np.interp(x_grid, x_values, power_values)

    return TechnologyGenerationResult(
        technology="",
        model_kind="curve",
        x=x_grid,
        y=None,
        power=power_grid,
    )


def generate_model_from_dataframe(
    df: pd.DataFrame,
    technology: str,
    x_column: str = "Depth",
    y_column: str = "Velocity",
    power_column: str = "Power",
    grid_points: int = 50,
) -> TechnologyGenerationResult:
    normalized_technology = _normalize_technology(technology)
    if normalized_technology in SURFACE_TECHNOLOGIES:
        result = _generate_surface_model(df, x_column, y_column, power_column, grid_points)
    else:
        result = _generate_curve_model(df, y_column, power_column, grid_points)
    result.technology = normalized_technology
    return result


def generate_model_from_csv(
    csv_path: str | Path,
    technology: str,
    x_column: str = "Depth",
    velocity_column: str = "Velocity",
    power_column: str = "Power",
    grid_points: int = 50,
) -> TechnologyGenerationResult:
    df = pd.read_csv(csv_path)
    return generate_model_from_dataframe(
        df=df,
        technology=technology,
        x_column=x_column,
        y_column=velocity_column,
        power_column=power_column,
        grid_points=grid_points,
    )


def save_generated_model(result: TechnologyGenerationResult, output_dir: str | Path, name: str) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    npz_path = output_dir / f"{name}.npz"
    csv_path = output_dir / f"{name}.csv"
    metadata = {"technology": result.technology, "model_kind": result.model_kind}

    if result.model_kind == "surface":
        np.savez(npz_path, grid_x=result.x, grid_y=result.y, grid_power=result.power, **metadata)
        flattened = pd.DataFrame(
            {"X": result.x.ravel(), "Y": result.y.ravel(), "Power": result.power.ravel()}
        )
    else:
        np.savez(npz_path, x=result.x, power=result.power, **metadata)
        flattened = pd.DataFrame({"X": result.x, "Power": result.power})

    flattened.to_csv(csv_path, index=False)

    return {"npz": str(npz_path), "csv": str(csv_path)}
