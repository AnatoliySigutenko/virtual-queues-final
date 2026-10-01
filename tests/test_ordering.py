from src.app.config import load_config
from src.app.state import StateManager
from src.app.models import Telemetry

def test_duplicates_and_out_of_order_are_ignored():
    cfg = load_config()
    state = StateManager(cfg)
    assert state.apply(Telemetry("T01", 100, 49.1201, 142.6501, 0))
    assert not state.apply(Telemetry("T01", 100, 49.1201, 142.6501, 0))
    assert not state.apply(Telemetry("T01", 99, 49.1201, 142.6501, 0))
    assert state.units["T01"].last_ts == 100
    assert state.apply(Telemetry("T01", 101, 49.1201, 142.6501, 0))
