from src.simulator.simulator import interpolate
from src.app.config import Point
from src.app.geo import distance_m

def test_interpolate():
    a = Point(0, 0)
    b = Point(0, 1)
    p = interpolate(a, b, distance_m(a, b) / 2)
    assert abs(p.lon - 0.5) < 0.01
