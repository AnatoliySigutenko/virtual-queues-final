from app.config import load_config
from app.models import Position, UnitState, TravelState
from app.state import StateManager
from app.queue_engine import QueueEngine
from app.models import Telemetry

def make_state():
    cfg = load_config()
    state = StateManager(cfg)
    return cfg, state, QueueEngine(cfg, state.units, state.stations)

def test_station_occupation_and_free_at():
    cfg, state, queues = make_state()
    state.apply(Telemetry("T01", 1000, 49.1201, 142.6501, 0))
    s = state.stations["S1"]
    assert s.occupied_by == "T01"
    assert s.occupied_at == 1000
    snap = queues.build_station_queue("S1", 1000)
    assert snap.queue[0].free_at == 1230

def test_queue_waiting_time():
    cfg, state, queues = make_state()
    state.apply(Telemetry("T01", 1000, 49.1201, 142.6501, 0))
    # T02 is about 1200m away, roughly 120s at 10m/s.
    state.apply(Telemetry("T02", 1000, 49.1308, 142.6501, 36))
    snap = queues.build_station_queue("S1", 1000)
    assert snap.queue[0].unit_uuid == "T01"
    assert snap.queue[1].unit_uuid == "T02"
    assert snap.queue[1].wait_seconds >= 0

def test_stale_unit_excluded():
    cfg, state, queues = make_state()
    state.apply(Telemetry("T01", 1000, 49.1201, 142.6501, 0))
    state.apply(Telemetry("T02", 900, 49.1308, 142.6501, 36))
    snap = queues.build_station_queue("S1", 1000)
    assert [x.unit_uuid for x in snap.queue] == ["T01"]

def test_horizon_excludes_far_eta():
    cfg, state, queues = make_state()
    state.apply(Telemetry("T02", 1000, 49.3500, 142.6501, 36))
    snap = queues.build_station_queue("S1", 1000)
    assert not any(x.unit_uuid == "T02" for x in snap.queue)


def test_station_frees_at_230_seconds_without_exit_message():
    cfg, state, queues = make_state()
    state.apply(Telemetry("T01", 1000, 49.1201, 142.6501, 0))
    state.expire_station_occupancy(1230)
    assert state.stations["S1"].occupied_by is None
    snap = queues.build_station_queue("S1", 1230)
    assert not snap.queue

def test_station_frees_early_when_machine_leaves_radius():
    cfg, state, queues = make_state()
    state.apply(Telemetry("T01", 1000, 49.1201, 142.6501, 0))
    state.apply(Telemetry("T01", 1050, 49.1210, 142.6501, 36))
    assert state.stations["S1"].occupied_by is None
