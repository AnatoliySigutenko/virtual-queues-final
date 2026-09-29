from .config import AppConfig, Point
from .geo import distance_m
from .models import Decision, UnitState
from .queue_engine import QueueSnapshot

class DecisionEngine:
    def __init__(self, config: AppConfig):
        self.config = config

    def _arrival(self, unit: UnitState, station_uuid: str, now: int) -> int | None:
        if unit.last_position is None:
            return None
        p = Point(unit.last_position.lat, unit.last_position.lon)
        station = self.config.stations[station_uuid]
        return now + int(round(distance_m(p, station.point) / self.config.processing.travel_speed_mps))

    def _wait(self, snapshot: QueueSnapshot, arrival: int, now: int, exclude_unit: str) -> int:
        blocking_free_at = now
        for item in snapshot.queue:
            if item.unit_uuid == exclude_unit:
                continue
            item_arrival = now if item.eta is None else item.eta
            if item_arrival <= arrival:
                blocking_free_at = max(blocking_free_at, item.free_at)
        return max(0, blocking_free_at - arrival)

    def choose(self, unit: UnitState, snapshots: dict[str, QueueSnapshot], now: int) -> Decision:
        own = unit.home_station
        arrivals = {sid: self._arrival(unit, sid, now) for sid in self.config.stations}
        waits = {sid: self._wait(snapshots[sid], eta, now, unit.unit_uuid) for sid, eta in arrivals.items() if eta is not None}
        if own not in waits:
            return Decision(unit.unit_uuid, now, "rejected", own, reason="stale_telemetry")

        own_wait = waits[own]
        best_wait = min(waits.values())
        tied = [sid for sid, wait in waits.items() if wait == best_wait]
        if own in tied:
            chosen = own
        else:
            pos = Point(unit.last_position.lat, unit.last_position.lon)
            chosen = min(tied, key=lambda sid: distance_m(pos, self.config.stations[sid].point))

        gain = own_wait - waits[chosen]
        if gain < self.config.processing.min_gain_seconds:
            return Decision(unit.unit_uuid, now, "rejected", own, gain_seconds=gain, reason="no_gain")
        return Decision(unit.unit_uuid, now, "recommended", own, to_station=chosen, gain_seconds=gain)
