from app.utils.geo import simplify_polyline


def test_simplify_removes_collinear_points():
    points = [[0.0, 0.0], [0.0, 0.5], [0.0, 1.0]]
    assert simplify_polyline(points, tolerance=0.0001) == [[0.0, 0.0], [0.0, 1.0]]


def test_simplify_keeps_zigzag_with_zero_tolerance():
    points = [[0.0, 0.0], [0.1, 0.0], [0.0, 0.1], [1.0, 1.0]]
    simplified = simplify_polyline(points, tolerance=0.0)
    assert len(simplified) == len(points)


def test_simplify_limits_max_points():
    points = [[float(index), float(index % 2)] for index in range(100)]
    simplified = simplify_polyline(points, tolerance=0.0, max_points=10)
    assert len(simplified) == 10
    assert simplified[0] == points[0]
    assert simplified[-1] == points[-1]


def test_simplify_short_input_is_returned_as_is():
    assert simplify_polyline([[1, 2]]) == [[1.0, 2.0]]
