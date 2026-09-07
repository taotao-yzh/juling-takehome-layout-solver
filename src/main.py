from __future__ import annotations

import json
import sys
from pathlib import Path

from .models import RoomInput
from .solver import solve
from .visualize import render_solution


def load_problem(path: Path) -> RoomInput:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return RoomInput(
        boundary=[tuple(p) for p in data["boundary"]],
        door=[tuple(p) for p in data["door"]],
        is_open_inward=bool(data.get("isOpenInward", False)),
        algo_to_place={k: tuple(v) for k, v in data["algoToPlace"].items()},
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python -m src.main <input.json>")
        return 1

    input_path = Path(argv[1])
    problem = load_problem(input_path)
    result = solve(problem)

    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    output_json = output_dir / f"{stem}_output.json"
    output_png = output_dir / f"{stem}.png"

    out = {
        "feasible": result.feasible,
        "reason": result.reason,
        "placements": [
            {
                "name": p.name,
                "center": [round(p.center[0], 4), round(p.center[1], 4)],
                "rotation": round(p.rotation % 360.0, 4),
                "length": p.length,
                "width": p.width,
            }
            for p in result.placements
        ],
    }
    output_json.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    render_solution(problem, result.placements, output_png)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Saved: {output_json}")
    print(f"Saved: {output_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
