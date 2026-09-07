from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

from shapely.affinity import rotate as shp_rotate, translate as shp_translate
from shapely.geometry import LineString, Point, Polygon

from .models import Point as Point2D

EPS = 1e-7


def distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def normalize_angle(angle: float) -> float:
    angle = angle % 360.0
    if angle < 0:
        angle += 360.0
    return angle


def remove_duplicate_closing_point(points: Sequence[Point2D]) -> List[Point2D]:
    pts = list(points)
    if len(pts) >= 2 and distance(pts[0], pts[-1]) <= EPS:
        pts.pop()
    return pts


def to_polygon(points: Sequence[Point2D]) -> Polygon:
    pts = remove_duplicate_closing_point(points)
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def segment_angle(a: Point2D, b: Point2D) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def unit_vector_from_angle(angle_deg: float) -> Tuple[float, float]:
    rad = math.radians(angle_deg)
    return math.cos(rad), math.sin(rad)


def perpendicular(v: Tuple[float, float]) -> Tuple[float, float]:
    return (-v[1], v[0])


def polygon_edges(points: Sequence[Point2D]):
    pts = remove_duplicate_closing_point(points)
    n = len(pts)
    for i in range(n):
        yield pts[i], pts[(i + 1) % n]


def rotate_rectangle(center: Point2D, length: float, width: float, angle_deg: float) -> Polygon:
    cx, cy = center
    half_l = length / 2.0
    half_w = width / 2.0
    rect = Polygon([(-half_l, -half_w), (half_l, -half_w), (half_l, half_w), (-half_l, half_w)])
    rect = shp_rotate(rect, angle_deg, origin=(0, 0), use_radians=False)
    rect = shp_translate(rect, cx, cy)
    return rect


def polygon_contains_polygon(outer: Polygon, inner: Polygon) -> bool:
    return outer.buffer(EPS).covers(inner)


def polygons_overlap(a: Polygon, b: Polygon) -> bool:
    inter = a.intersection(b)
    return inter.area > 1e-6


def line_buffer(line: Sequence[Point2D], width: float) -> Polygon:
    return LineString(line).buffer(width / 2.0, cap_style=2, join_style=2)


def rectangle_from_midpoint(center: Point2D, angle_deg: float, length: float, width: float) -> Polygon:
    return rotate_rectangle(center, length, width, angle_deg)


def edge_length(a: Point2D, b: Point2D) -> float:
    return distance(a, b)


def edge_direction(a: Point2D, b: Point2D) -> Tuple[float, float]:
    d = distance(a, b)
    if d <= EPS:
        return 0.0, 0.0
    return (b[0] - a[0]) / d, (b[1] - a[1]) / d


def point_inside_polygon(poly: Polygon, p: Point2D) -> bool:
    return poly.buffer(EPS).covers(Point(p))
