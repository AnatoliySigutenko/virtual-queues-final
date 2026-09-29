import asyncio
import json
import logging
from datetime import datetime, timezone
from .config import load_config, Point
from .models import Telemetry, TravelState
from .state import StateManager
from .queue_engine import QueueEngine
from .decision_engine import DecisionEngine
from .geo import distance_m

log = logging.getLogger("virtual-queues")

def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")

def queue_payload(snapshot):
    return {
        "station_uuid": snapshot.station_uuid,
        "at": iso(snapshot.at),
        "queue": [
            {"unit_uuid": x.unit_uuid,
             "eta": None if x.eta is None else iso(x.eta),
             "service_start": iso(x.service_start),
             "free_at": iso(x.free_at),
             "wait_seconds": x.wait_seconds}
            for x in snapshot.queue
        ],
    }

def decision_payload(d):
    out = {"unit_uuid": d.unit_uuid, "at": iso(d.at), "result": d.result, "from_station": d.from_station}
    if d.result == "recommended":
        out.update(to_station=d.to_station, gain_seconds=d.gain_seconds)
    else:
        out["reason"] = d.reason
        if d.gain_seconds is not None:
            out["gain_seconds"] = d.gain_seconds
    return out

async def run(config_path="config/config.yaml"):
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
    cfg = load_config(config_path)
    state = StateManager(cfg)
    queues = QueueEngine(cfg, state.units, state.stations)
    decisions = DecisionEngine(cfg)
    consumer = AIOKafkaConsumer(
        cfg.telemetry_topic, bootstrap_servers=cfg.kafka_bootstrap,
        group_id=cfg.group_id, enable_auto_commit=False, auto_offset_reset="earliest"
    )
    producer = AIOKafkaProducer(bootstrap_servers=cfg.kafka_bootstrap, enable_idempotence=True)
    await consumer.start(); await producer.start()
    try:
        async for msg in consumer:
            event = Telemetry(**json.loads(msg.value))
            if not state.apply(event):
                await consumer.commit(); continue
            now = max(u.last_ts for u in state.units.values() if u.last_ts is not None)
            state.expire_station_occupancy(now)
            snapshots = queues.rebuild_all(now)
            for sid, snapshot in snapshots.items():
                key = QueueEngine.snapshot_key(snapshot)
                if state.stations[sid].last_snapshot != key:
                    await producer.send_and_wait(cfg.queue_topic, key=sid.encode(), value=json.dumps(queue_payload(snapshot)).encode())
                    state.stations[sid].last_snapshot = key

            unit = state.units[event.unit_uuid]
            if unit.state == TravelState.TO_STATION and not unit.recommendation_active and unit.last_position:
                home = cfg.stations[unit.home_station]
                d = distance_m(Point(unit.last_position.lat, unit.last_position.lon), home.point)
                inside = d <= cfg.processing.decision_radius_m
                crossed = inside and not unit.was_in_decision_zone
                if crossed:
                    stale = now - event.ts > cfg.processing.freshness_seconds
                    decision = (decisions.choose(unit, snapshots, now)
                                if not stale else __import__("app.models", fromlist=["Decision"]).Decision(
                                    unit.unit_uuid, now, "rejected", unit.home_station, reason="stale_telemetry"))
                    await producer.send_and_wait(cfg.decision_topic, key=unit.unit_uuid.encode(), value=json.dumps(decision_payload(decision)).encode())
                    unit.last_decision_trigger_ts = event.ts
                    if decision.result == "recommended":
                        unit.recommendation_active = True
                        unit.recommended_station = decision.to_station
                        unit.station_arrival_at = None
                unit.was_in_decision_zone = inside
            await consumer.commit()
    finally:
        await consumer.stop(); await producer.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
