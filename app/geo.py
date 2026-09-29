from math import radians, sin, cos, sqrt, atan2
from .config import Point

EARTH_RADIUS_M = 6_371_000.0

def distance_m(a: Point, b: Point) -> float:
    lat1, lat2 = radians(a.lat), radians(b.lat)
    dlat = radians(b.lat - a.lat)
    dlon = radians(b.lon - a.lon)
    h = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    return 2 * EARTH_RADIUS_M * atan2(sqrt(h), sqrt(max(0.0, 1 - h)))

def point_from_telemetry(lat: float, lon: float) -> Point:
    return Point(lat, lon)
