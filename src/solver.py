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
        rot_rad = math.radians(rotation)
        ux, uy = math.cos(rot_rad), math.sin(rot_rad)   # length 方向单位向量
        vx, vy = -math.sin(rot_rad), math.cos(rot_rad)  # width 方向单位向量
        for edge_a, edge_b in polygon_edges(list(room.exterior.coords)):
            if edge_length(edge_a, edge_b) <= EPS:
                continue
            ex, ey = edge_direction(edge_a, edge_b)
            nx, ny = -ey, ex
            # 法线必须指向房间内部，否则这面墙的贴墙候选会生成在墙外被全面丢弃
            mid = ((edge_a[0] + edge_b[0]) / 2.0, (edge_a[1] + edge_b[1]) / 2.0)
            if not room.buffer(EPS).covers(Point(mid[0] + nx * 5.0, mid[1] + ny * 5.0)):
                nx, ny = -nx, -ny
            # 贴墙时中心沿法线内缩的距离 = 物品在法线方向上的半尺寸。
            # 法线与 length 轴对齐 -> half_l；与 width 轴对齐 -> half_w。
            # 原先无条件用 half_w，物品旋转 90° 后贴墙点算错被丢弃，导致退化为网格撒点、不贴墙。
            half_normal = half_l if abs(nx * ux + ny * uy) >= abs(nx * vx + ny * vy) else half_w
            wall_len = edge_length(edge_a, edge_b)
            samples = max(1, int(wall_len // step))
            for i in range(samples + 1):
                t = 0 if samples == 0 else i / samples
                px = edge_a[0] + ex * wall_len * t
                py = edge_a[1] + ey * wall_len * t
                inward_center = (
                    px + nx * half_normal,
                    py + ny * half_normal,
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


def fridge_keepout(room: Polygon, candidate: Candidate, item: ItemSpec) -> Polygon:
    # 题目要求：冰箱 length 的其中一边为开门边，开门边不能放任何东西。
    # 因此禁放区必须位于 length 端面外侧（而不是原先的 width 端面外侧）。
    # 冰箱可能在墙边，门只能朝房间内部开，所以取 length 两端中
    # 禁放条带深入房间内部更多（离墙更远）的那一端。
    front_depth = max(item.length, 600.0)
    cx, cy = candidate.center
    ang = math.radians(candidate.rotation)
    ux, uy = math.cos(ang), math.sin(ang)      # length 方向
    vx, vy = -math.sin(ang), math.cos(ang)     # width 方向
    half_l = item.length / 2.0
    half_w = item.width / 2.0

    def build(sign: float) -> Polygon:
        front_mid = (cx + ux * sign * half_l, cy + uy * sign * half_l)
        p0 = (front_mid[0] - vx * half_w, front_mid[1] - vy * half_w)
        p1 = (front_mid[0] + vx * half_w, front_mid[1] + vy * half_w)
        p2 = (p1[0] + ux * sign * front_depth, p1[1] + uy * sign * front_depth)
        p3 = (p0[0] + ux * sign * front_depth, p0[1] + uy * sign * front_depth)
        return Polygon([p0, p1, p2, p3])

    strip_pos = build(+1.0)
    strip_neg = build(-1.0)
    inner_ref = room.buffer(EPS)
    if inner_ref.intersection(strip_pos).area >= inner_ref.intersection(strip_neg).area:
        return strip_pos
    return strip_neg


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
                extra_obstacles.append(fridge_keepout(room, cand, item))
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
