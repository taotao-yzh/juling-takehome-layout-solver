from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

Point = Tuple[float, float]
Size = Tuple[float, float]


@dataclass(frozen=True)
class RoomInput:
    boundary: List[Point]
    door: List[Point]
    is_open_inward: bool
    algo_to_place: Dict[str, Size]


@dataclass(frozen=True)
class ItemSpec:
    name: str
    length: float
    width: float

    @property
    def area(self) -> float:
        return self.length * self.width

    @property
    def kind(self) -> str:
        if self.name.startswith("fridge"):
            return "fridge"
        if self.name.startswith("iceMaker"):
            return "iceMaker"
        if self.name.startswith("overShelf"):
            return "overShelf"
        if self.name.startswith("shelf"):
            return "shelf"
        return "other"


@dataclass(frozen=True)
class Placement:
    name: str
    center: Point
    rotation: float
    length: float
    width: float


@dataclass(frozen=True)
class SolveResult:
    feasible: bool
    placements: List[Placement]
    reason: str | None = None
