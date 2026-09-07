from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from shapely.geometry import Point, Polygon

from .geometry import (
    EPS,
    edge_direction,
    edge_length,
    line_buffer,
    normalize_angle,
    point_inside_polygon,
    polygon_contains_polygon,
    polygon_edges,
    polygons_overlap,
    rotate_rectangle,
    segment_angle,
    to_polygon,
    unit_vector_from_angle,
)
from .models import ItemSpec, Placement, RoomInput, SolveResult


@dataclass(frozen=True)
class Candidate:
    center: Tuple[float, float]
    rotation: float
    polygon: Polygon


def parse_items(algo_to_place: Dict[str, Tuple[float, float]]) -> List[ItemSpec]:
    items = [ItemSpec(name=name, length=size[0], width=size[1]) for name, size in algo_to_place.items()]
    items.sort(key=lambda x: (0 if x.kind == "fridge" else 1 if x.kind == "iceMaker" else 2, -x.area))
    return items


def compute_door_obstacles(room: Polygon, door: List[Tuple[float, float]], is_open_inward: bool) -> List[Polygon]:
    d0, d1 = door
    door_width = math.hypot(d1[0] - d0[0], d1[1] - d0[1])
    obstacles = [line_buffer(door, max(door_width * 0.06, 20.0))]
    if not is_open_inward:
        return obstacles

    mid = ((d0[0] + d1[0]) / 2.0, (d0[1] + d1[1]) / 2.0)
    dx, dy = d1[0] - d0[0], d1[1] - d0[1]
    dlen = math.hypot(dx, dy)
    if dlen <= EPS:
        return obstacles

    n1 = (-dy / dlen, dx / dlen)
    n2 = (dy / dlen, -dx / dlen)
    test1 = Point(mid[0] + n1[0] * 5.0, mid[1] + n1[1] * 5.0)
    inward = n1 if room.buffer(EPS).covers(test1) else n2
    p0 = d0
    p1 = d1
    p2 = (d1[0] + inward[0] * door_width, d1[1] + inward[1] * door_width)
    p3 = (d0[0] + inward[0] * door_width, d0[1] + inward[1] * door_width)
    obstacles.append(Polygon([p0, p1, p2, p3]))
    return obstacles


def item_candidates(room: Polygon, item: ItemSpec, door_obstacles: List[Polygon]) -> List[Candidate]:
    candidates: List[Candidate] = []
    room_angle = dominant_room_angle(room)
    rotations = [normalize_angle(room_angle), normalize_angle(room_angle + 90.0)]
    if item.kind == "fridge":
        rotations = [normalize_angle(room_angle), normalize_angle(room_angle + 90.0)]

    minx, miny, maxx, maxy = room.bounds
    step = 100.0

    for rotation in rotations:
        half_l = item.length / 2.0
        half_w = item.width / 2.0
        for edge_a, edge_b in polygon_edges(list(room.exterior.coords)):
            if edge_length(edge_a, edge_b) <= EPS:
                continue
            ex, ey = edge_direction(edge_a, edge_b)
            nx, ny = -ey, ex
            edge_ang = segment_angle(edge_a, edge_b)
            # wall-adjacent candidates
            wall_dir = (ex, ey)
            wall_len = edge_length(edge_a, edge_b)
            samples = max(1, int(wall_len // step))
            for i in range(samples + 1):
                t = 0 if samples == 0 else i / samples
                px = edge_a[0] + wall_dir[0] * wall_len * t
                py = edge_a[1] + wall_dir[1] * wall_len * t
                inward_center = (
                    px + nx * half_w,
                    py + ny * half_w,
                )
                rect = rotate_rectangle(inward_center, item.length, item.width, rotation)
                if room.buffer(EPS).covers(rect) and all(not rect.intersects(obs) for obs in door_obstacles):
                    candidates.append(Candidate(inward_center, rotation, rect))

        # coarse interior fallback
        gx = minx
        while gx <= maxx:
            gy = miny
            while gy <= maxy:
                rect = rotate_rectangle((gx, gy), item.length, item.width, rotation)
                if room.buffer(EPS).covers(rect) and all(not rect.intersects(obs) for obs in door_obstacles):
                    candidates.append(Candidate((gx, gy), rotation, rect))
                gy += step
            gx += step

    # deterministic de-duplication
    seen = set()
    unique: List[Candidate] = []
    for c in candidates:
        key = (round(c.center[0], 3), round(c.center[1], 3), round(c.rotation % 360.0, 3))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def dominant_room_angle(room: Polygon) -> float:
    lengths: Dict[float, float] = {}
    coords = list(room.exterior.coords)
    for a, b in zip(coords, coords[1:]):
        ang = normalize_angle(segment_angle(a, b))
        ang = round(ang % 180.0, 1)
        lengths[ang] = lengths.get(ang, 0.0) + edge_length(a, b)
    if not lengths:
        return 0.0
    best = max(lengths.items(), key=lambda kv: kv[1])[0]
    return best


def fridge_keepout(candidate: Candidate, item: ItemSpec) -> Polygon:
    # Conservative keep-out in front of the fridge along the positive local y direction.
    front_depth = max(item.width, 600.0)
    base = rotate_rectangle(candidate.center, item.length, item.width, candidate.rotation)
    # Build a keep-out strip extending from the front edge.
    cx, cy = candidate.center
    ang = math.radians(candidate.rotation)
    ux, uy = math.cos(ang), math.sin(ang)
    vx, vy = -math.sin(ang), math.cos(ang)
    half_l = item.length / 2.0
    half_w = item.width / 2.0
    front_mid = (cx + vx * half_w, cy + vy * half_w)
    p0 = (front_mid[0] - ux * half_l, front_mid[1] - uy * half_l)
    p1 = (front_mid[0] + ux * half_l, front_mid[1] + uy * half_l)
    p2 = (p1[0] + vx * front_depth, p1[1] + vy * front_depth)
    p3 = (p0[0] + vx * front_depth, p0[1] + vy * front_depth)
    return Polygon([p0, p1, p2, p3])


def can_place(candidate: Candidate, room: Polygon, placed: List[Placement], obstacles: List[Polygon]) -> bool:
    poly = candidate.polygon
    if not room.buffer(EPS).covers(poly):
        return False
    for obs in obstacles:
        if poly.intersection(obs).area > 1e-6:
            return False
    for p in placed:
        other = rotate_rectangle(p.center, p.length, p.width, p.rotation)
        if poly.intersection(other).area > 1e-6:
            return False
    return True


def solve(room_input: RoomInput) -> SolveResult:
    room = to_polygon(room_input.boundary)
    items = parse_items(room_input.algo_to_place)
    door_obstacles = compute_door_obstacles(room, room_input.door, room_input.is_open_inward)

    candidate_map: Dict[str, List[Candidate]] = {}
    for item in items:
        candidate_map[item.name] = item_candidates(room, item, door_obstacles)
        if not candidate_map[item.name]:
            return SolveResult(False, [], f"No candidates found for {item.name}")

    placements: List[Placement] = []
    extra_obstacles = list(door_obstacles)

    def dfs(idx: int) -> bool:
        nonlocal extra_obstacles
        if idx == len(items):
            return True
        item = items[idx]
        for cand in candidate_map[item.name]:
            if not can_place(cand, room, placements, extra_obstacles):
                continue
            placements.append(
                Placement(
                    name=item.name,
                    center=cand.center,
                    rotation=cand.rotation,
                    length=item.length,
                    width=item.width,
                )
            )
            pushed = False
            if item.kind == "fridge":
                extra_obstacles.append(fridge_keepout(cand, item))
                pushed = True
            if dfs(idx + 1):
                return True
            if pushed:
                extra_obstacles.pop()
            placements.pop()
        return False

    feasible = dfs(0)
    if not feasible:
        return SolveResult(False, [], "No feasible placement found")
    return SolveResult(True, placements, None)
