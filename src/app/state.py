from .config import AppConfig, Point
from .geo import distance_m
from .models import Telemetry, UnitState, StationState, TravelState, Position

class StateManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self.units = {
            uuid: UnitState(uuid, cfg.home_station)
            for uuid, cfg in config.units.items()
        }
        self.stations = {uuid: StationState(uuid) for uuid in config.stations}

    def expire_station_occupancy(self, now: int) -> None:
        """Apply the deterministic 230s maximum occupation rule in event time."""
        duration = self.config.processing.service_seconds + self.config.processing.maneuver_seconds
        for station in self.stations.values():
            if station.occupied_by is not None and station.occupied_at is not None:
                if now >= station.occupied_at + duration:
                    unit = self.units.get(station.occupied_by)
                    if unit is not None and unit.state == TravelState.AT_STATION:
                        # The unit is no longer considered to occupy the resource.
                        unit.occupied_at = None
                    station.occupied_by = None
                    station.occupied_at = None

    def apply(self, event: Telemetry) -> bool:
        unit = self.units.get(event.unit_uuid)
        if unit is None:
            return False
        if unit.last_ts is not None and event.ts <= unit.last_ts:
            return False

        unit.last_ts = event.ts
        unit.last_position = Position(event.lat, event.lon, event.speed_kmh, event.ts)
        pos = Point(event.lat, event.lon)

        target_station_uuid = (
            unit.recommended_station
            if unit.recommendation_active and unit.recommended_station
            else unit.home_station
        )
        target_station = self.config.stations[target_station_uuid]
        d_target = distance_m(pos, target_station.point)
        in_station_radius = d_target < self.config.processing.station_radius_m
        # Arrival is defined by entering the 50m radius, independently of speed.
        if in_station_radius:
            unit.station_arrival_at = unit.station_arrival_at or event.ts

        at_station = (
            event.speed_kmh < self.config.processing.stopped_speed_kmh
            and in_station_radius
        )

        if at_station:
            station = self.stations[target_station_uuid]
            if station.occupied_by is None:
                station.occupied_by = unit.unit_uuid
                station.occupied_at = event.ts
                unit.state = TravelState.AT_STATION
                unit.current_station = target_station_uuid
                unit.occupied_at = event.ts
                unit.recommendation_active = False
                unit.recommended_station = None
                unit.was_in_decision_zone = False
            elif station.occupied_by == unit.unit_uuid:
                unit.state = TravelState.AT_STATION
            else:
                # The machine has arrived but cannot occupy the station yet.
                unit.state = TravelState.TO_STATION
            return True

        if unit.state == TravelState.AT_STATION:
            occupied_station = unit.current_station or unit.home_station
            station = self.stations[occupied_station]
            if station.occupied_by == unit.unit_uuid:
                station.occupied_by = None
                station.occupied_at = None
            unit.state = TravelState.TO_UNLOADING
            unit.occupied_at = None
            unit.station_arrival_at = None
            unit.was_in_decision_zone = False
            return True

        if unit.recommendation_active:
            # It remains on the trip to the recommended station until it reaches it.
            unit.state = TravelState.TO_STATION
            return True

        # A unit reaches the unloading point, then starts the next trip to its home station.
        unload_d = distance_m(pos, self.config.unloading)
        if unload_d >= self.config.processing.unloading_radius_m:
            unit.state = TravelState.TO_STATION
            unit.station_arrival_at = None
            unit.was_in_decision_zone = False
        return True
