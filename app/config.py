from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass(frozen=True)
class Point:
    lat: float
    lon: float

@dataclass(frozen=True)
class Station:
    uuid: str
    point: Point

@dataclass(frozen=True)
class UnitConfig:
    uuid: str
    home_station: str

@dataclass(frozen=True)
class ProcessingConfig:
    service_seconds: int
    maneuver_seconds: int
    travel_speed_mps: float
    station_radius_m: float
    unloading_radius_m: float
    stopped_speed_kmh: float
    decision_radius_m: float
    queue_horizon_seconds: int
    freshness_seconds: int
    min_gain_seconds: int

@dataclass(frozen=True)
class AppConfig:
    kafka_bootstrap: str
    telemetry_topic: str
    queue_topic: str
    decision_topic: str
    group_id: str
    unloading: Point
    stations: dict[str, Station]
    units: dict[str, UnitConfig]
    processing: ProcessingConfig

def load_config(path: str | Path = "config/config.yaml") -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text())
    p = raw["processing"]
    processing = ProcessingConfig(**p)
    stations = {
        x["uuid"]: Station(x["uuid"], Point(x["lat"], x["lon"]))
        for x in raw["stations"]
    }
    units = {
        x["uuid"]: UnitConfig(x["uuid"], x["home_station"])
        for x in raw["units"]
    }
    k = raw["kafka"]
    u = raw["unloading"]
    return AppConfig(
        kafka_bootstrap=k["bootstrap_servers"],
        telemetry_topic=k["telemetry_topic"],
        queue_topic=k["queue_topic"],
        decision_topic=k["decision_topic"],
        group_id=k["group_id"],
        unloading=Point(u["lat"], u["lon"]),
        stations=stations,
        units=units,
        processing=processing,
    )
