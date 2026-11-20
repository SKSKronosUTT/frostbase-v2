"""Utilidades geográficas."""

from __future__ import annotations

import math
from typing import Iterable

Point = list[float] | tuple[float, float]


def _segment_distance(point: Point, start: Point, end: Point) -> float:
    """Distancia aproximada punto-segmento en metros (proyección local)."""
    lat0 = math.radians((start[0] + end[0]) / 2)
    scale_x = 111_320.0 * math.cos(lat0)
    scale_y = 111_320.0

    px, py = point[1] * scale_x, point[0] * scale_y
    ax, ay = start[1] * scale_x, start[0] * scale_y
    bx, by = end[1] * scale_x, end[0] * scale_y

    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def simplify_polyline(
    points: Iterable[Point],
    tolerance: float = 0.0001,
    max_points: int = 400,
) -> list[list[float]]:
    """Simplifica una polilínea con Ramer–Douglas–Peucker.

    ``tolerance`` se interpreta en grados (0.0001 ≈ 11 m). Si el resultado aún
    supera ``max_points``, se muestrea de forma uniforme conservando extremos.
    """
    coordinates = [[float(point[0]), float(point[1])] for point in points]
    if len(coordinates) <= 2:
        return coordinates

    tolerance_m = max(0.0, tolerance) * 111_320.0
    keep = [False] * len(coordinates)
    keep[0] = keep[-1] = True
    stack = [(0, len(coordinates) - 1)]

    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        max_distance = -1.0
        index = -1
        for position in range(start + 1, end):
            distance = _segment_distance(
                coordinates[position], coordinates[start], coordinates[end]
            )
            if distance > max_distance:
                max_distance = distance
                index = position
        if index != -1 and max_distance > tolerance_m:
            keep[index] = True
            stack.append((start, index))
            stack.append((index, end))

    simplified = [point for point, selected in zip(coordinates, keep) if selected]
    if len(simplified) > max_points > 2:
        step = (len(simplified) - 1) / (max_points - 1)
        simplified = [
            simplified[min(len(simplified) - 1, round(index * step))]
            for index in range(max_points)
        ]
    return simplified
