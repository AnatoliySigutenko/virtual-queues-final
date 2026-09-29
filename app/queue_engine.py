from dataclasses import dataclass
from .config import AppConfig, Point
from .geo import distance_m
from .models import UnitState, StationState, TravelState, QueueItem

@dataclass(frozen=True)
class QueueSnapshot:
    station_uuid: str
    at: int
    queue: tuple[QueueItem, ...]

class QueueEngine:
    def __init__(self, config: AppConfig, units: dict[str, UnitState], stations: dict[str, StationState]):
        self.config = config
        self.units = units
        self.stations = stations

    def eta_to_station(self, unit: UnitState, station_uuid: str, now: int) -> int | None:
        if unit.last_position is None or unit.last_ts is None:
            return None
        station = self.config.stations[station_uuid]
        pos = Point(unit.last_position.lat, unit.last_position.lon)
        speed = self.config.processing.travel_speed_mps

        # Once the machine has entered the target radius, its arrival is the
        # first event timestamp in that radius, not a new geometric ETA.
        target = unit.recommended_station if unit.recommendation_active else unit.home_station
        if station_uuid == target and unit.station_arrival_at is not None:
            return unit.station_arrival_at

        if unit.state == TravelState.TO_STATION:
            seconds = distance_m(pos, station.point) / speed
        elif unit.state == TravelState.TO_UNLOADING:
            seconds = (
                distance_m(pos, self.config.unloading)
                + distance_m(self.config.unloading, station.point)
            ) / speed
        else:
            return None
        return now + int(round(seconds))

    def _fresh(self, unit: UnitState, now: int) -> bool:
        return unit.last_ts is not None and now - unit.last_ts <= self.config.processing.freshness_seconds

    def build_station_queue(self, station_uuid: str, now: int) -> QueueSnapshot:
        p = self.config.processing
        station = self.stations[station_uuid]
        duration = p.service_seconds + p.maneuver_seconds

        actual: list[QueueItem] = []
        occupied = station.occupied_by is not None and station.occupied_at is not None
        if occupied:
            free_at = station.occupied_at + duration
            if free_at > now:
                actual.append(QueueItem(station.occupied_by, None, station.occupied_at, free_at, 0))

        candidates: list[tuple[int, str]] = []
        for unit in self.units.values():
            if unit.unit_uuid == station.occupied_by:
                continue
            if not self._fresh(unit, now):
                continue
            if unit.recommendation_active and unit.recommended_station != station_uuid:
                continue
            eta = self.eta_to_station(unit, station_uuid, now)
            if eta is None or eta > now + p.queue_horizon_seconds:
                continue
            # A unit that is already at a different station is never a candidate.
            if unit.state == TravelState.AT_STATION:
                continue
            candidates.append((eta, unit.unit_uuid))

        candidates.sort(key=lambda x: (x[0], x[1]))
        result = actual[:]
        previous_free = actual[-1].free_at if actual else now
        for eta, unit_uuid in candidates:
            start = max(eta, previous_free)
            free_at = start + duration
            result.append(QueueItem(unit_uuid, eta, start, free_at, max(0, start - eta)))
            previous_free = free_at
        return QueueSnapshot(station_uuid, now, tuple(result))

    def rebuild_all(self, now: int) -> dict[str, QueueSnapshot]:
        return {sid: self.build_station_queue(sid, now) for sid in self.config.stations}

    @staticmethod
    def snapshot_key(snapshot: QueueSnapshot) -> tuple:
        return tuple((x.unit_uuid, x.eta, x.service_start, x.free_at, x.wait_seconds) for x in snapshot.queue)
