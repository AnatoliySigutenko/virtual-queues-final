from src.app.config import load_config
from src.app.state import StateManager
from src.app.models import Telemetry, TravelState, QueueItem
from src.app.queue_engine import QueueEngine, QueueSnapshot
from src.app.decision_engine import DecisionEngine


def test_no_gain_when_all_stations_are_equivalent():
    cfg = load_config()
    state = StateManager(cfg)
    q = QueueEngine(cfg, state.units, state.stations)
    d = DecisionEngine(cfg)
    state.apply(Telemetry("T01", 1000, 49.1250, 142.6500, 36))
    snapshots = q.rebuild_all(1000)
    result = d.choose(state.units["T01"], snapshots, 1000)
    assert result.result == "rejected"
    assert result.reason == "no_gain"


def test_wait_excludes_candidate_itself_and_recommends_other_station():
    cfg = load_config()
    state = StateManager(cfg)
    d = DecisionEngine(cfg)
    unit = state.units["T01"]
    state.apply(Telemetry("T01", 1000, 49.1200, 142.6700, 36))

    # Home S1 has an existing machine that will block T01 for 200s+30s.
    busy = QueueSnapshot("S1", 1000, (
        QueueItem("T02", None, 900, 1500, 0),
        QueueItem("T01", 1060, 1500, 1730, 440),
    ))
    empty = QueueSnapshot("S2", 1000, ())
    snapshots = {"S1": busy, "S2": empty, "S3": QueueSnapshot("S3",1000,(QueueItem("T21", None, 900, 2000, 0),)), "S4": QueueSnapshot("S4",1000,(QueueItem("T31", None, 900, 2000, 0),))}
    result = d.choose(unit, snapshots, 1000)
    assert result.result == "recommended"
    assert result.to_station == "S2"
    assert result.gain_seconds >= 60


def test_recommended_station_becomes_target():
    cfg = load_config()
    state = StateManager(cfg)
    unit = state.units["T04"]
    unit.recommendation_active = True
    unit.recommended_station = "S2"
    unit.state = TravelState.TO_STATION
    state.apply(Telemetry("T04", 2000, 49.1201, 142.7501, 0))
    assert state.stations["S2"].occupied_by == "T04"
    assert state.stations["S1"].occupied_by is None
