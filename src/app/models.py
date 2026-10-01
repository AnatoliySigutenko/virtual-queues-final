from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class TravelState(str, Enum):
    AT_STATION = "at_station"
    TO_UNLOADING = "to_unloading"
    TO_STATION = "to_station"

@dataclass(frozen=True)
class Position:
    lat: float
    lon: float
    speed_kmh: float
    ts: int

@dataclass(frozen=True)
class Telemetry:
    unit_uuid: str
    ts: int
    lat: float
    lon: float
    speed_kmh: float

@dataclass
class UnitState:
    unit_uuid: str
    home_station: str
    last_ts: Optional[int] = None
    last_position: Optional[Position] = None
    state: TravelState = TravelState.TO_STATION
    current_station: Optional[str] = None
    occupied_at: Optional[int] = None
    # Timestamp at which the current trip reached the target station radius.
    station_arrival_at: Optional[int] = None
    recommendation_active: bool = False
    recommended_station: Optional[str] = None
    # Used to detect the first crossing into the 1500m decision zone.
    was_in_decision_zone: bool = False
    last_decision_trigger_ts: Optional[int] = None

@dataclass
class QueueItem:
    unit_uuid: str
    eta: Optional[int]
    service_start: int
    free_at: int
    wait_seconds: int

@dataclass
class StationState:
    station_uuid: str
    occupied_by: Optional[str] = None
    occupied_at: Optional[int] = None
    queue: list[QueueItem] = field(default_factory=list)
    last_snapshot: Optional[tuple] = None

@dataclass(frozen=True)
class Decision:
    unit_uuid: str
    at: int
    result: str
    from_station: str
    to_station: Optional[str] = None
    gain_seconds: Optional[int] = None
    reason: Optional[str] = None
