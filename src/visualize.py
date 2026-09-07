from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import Polygon

from .geometry import rotate_rectangle, to_polygon
from .models import Placement, RoomInput
from .solver import compute_door_obstacles, fridge_keepout


def _add_poly(ax, poly: Polygon, *, facecolor: str, edgecolor: str, alpha: float = 0.3, linestyle: str = "-") -> None:
    if poly.is_empty:
        return
    x, y = poly.exterior.xy
    patch = MplPolygon(list(zip(x, y)), closed=True, facecolor=facecolor, edgecolor=edgecolor, alpha=alpha, linestyle=linestyle)
    ax.add_patch(patch)


def render_solution(problem: RoomInput, placements: List[Placement], output_path: str | Path) -> None:
    room = to_polygon(problem.boundary)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 10))
    _add_poly(ax, room, facecolor="#f5f5f5", edgecolor="#333333", alpha=0.35)

    door_obstacles = compute_door_obstacles(room, problem.door, problem.is_open_inward)
    for i, obs in enumerate(door_obstacles):
        _add_poly(ax, obs, facecolor="#ffd166", edgecolor="#d97706", alpha=0.45 if i == 0 else 0.2, linestyle="--")

    for placement in placements:
        poly = rotate_rectangle(placement.center, placement.length, placement.width, placement.rotation)
        color = "#e45756" if placement.name.startswith("fridge") else "#4c78a8"
        _add_poly(ax, poly, facecolor=color, edgecolor="#1f2937", alpha=0.55)
        ax.text(placement.center[0], placement.center[1], placement.name, ha="center", va="center", fontsize=8, color="black")

        if placement.name.startswith("fridge"):
            dummy_candidate = type("DummyCandidate", (), {"center": placement.center, "rotation": placement.rotation})()
            dummy_item = type("DummyItem", (), {"length": placement.length, "width": placement.width})()
            keepout = fridge_keepout(room, dummy_candidate, dummy_item)
            _add_poly(ax, keepout, facecolor="#f28e2b", edgecolor="#b45309", alpha=0.18, linestyle="--")

    xs = [p[0] for p in problem.boundary]
    ys = [p[1] for p in problem.boundary]
    margin = max((max(xs) - min(xs)) * 0.08, (max(ys) - min(ys)) * 0.08, 100.0)
    ax.set_xlim(min(xs) - margin, max(xs) + margin)
    ax.set_ylim(min(ys) - margin, max(ys) + margin)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("TakeHome Layout Solution")
    ax.grid(True, linestyle=":", alpha=0.25)
    plt.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
