"""Deterministic Kafka telemetry generator with realistic station queues."""
import argparse
import asyncio
import json
import random
import time
from dataclasses import dataclass
from app.config import load_config, Point
from app.geo import distance_m

@dataclass(frozen=True)
class Trip:
    service_start: int
    service_end: int
    free_at: int
    unload_at: int
    next_home_arrival: int


def interpolate(a: Point, b: Point, distance: float) -> Point:
    total = distance_m(a, b)
    if total <= 0:
        return b
    f = min(1.0, max(0.0, distance / total))
    return Point(a.lat + (b.lat - a.lat) * f, a.lon + (b.lon - a.lon) * f)


def build_schedule(cfg, start_ts: int) -> dict[str, list[Trip]]:
    """Build deterministic cycles; station_free enforces the physical queue."""
    speed = cfg.processing.travel_speed_mps
    duration = cfg.processing.service_seconds + cfg.processing.maneuver_seconds
    schedules: dict[str, list[Trip]] = {}
    station_free = {sid: start_ts for sid in cfg.stations}

    # Stagger first arrivals to avoid a perfectly synchronized synthetic workload.
    for idx, unit in enumerate(cfg.units.values()):
        home = cfg.stations[unit.home_station].point
        route_s = int(round(distance_m(home, cfg.unloading) / speed))
        arrival = start_ts + (idx * 7)
        trips = []
        for _ in range(100):
            service_start = max(arrival, station_free[unit.home_station])
            service_end = service_start + cfg.processing.service_seconds
            free_at = service_start + duration
            unload_at = free_at + route_s
            next_arrival = unload_at + route_s
            trips.append(Trip(service_start, service_end, free_at, unload_at, next_arrival))
            station_free[unit.home_station] = free_at
            arrival = next_arrival
        schedules[unit.uuid] = trips
    return schedules


def telemetry_for(unit, ts: int, cfg, trips: list[Trip]):
    home = cfg.stations[unit.home_station].point
    unload = cfg.unloading
    speed = cfg.processing.travel_speed_mps
    route_s = distance_m(home, unload) / speed

    # Find the current cycle. The simulator runs forward, so linear scan is fine.
    trip = None
    for t in trips:
        if t.service_start <= ts < t.next_home_arrival:
            trip = t
            break
    if trip is None:
        trip = trips[-1]

    if ts < trip.service_end:
        return {"lat": home.lat, "lon": home.lon, "speed_kmh": 0.0}

    if ts < trip.free_at:
        # 30s maneuver segment, then regular travel. It starts at the station.
        d = min((ts - trip.service_end + 1) * speed, route_s)
        p = interpolate(home, unload, d)
        return {"lat": p.lat, "lon": p.lon, "speed_kmh": 36.0}

    if ts < trip.unload_at:
        d = min((ts - trip.free_at) * speed, route_s)
        p = interpolate(home, unload, d)
        return {"lat": p.lat, "lon": p.lon, "speed_kmh": 36.0}

    # After unloading, drive back to the home station. If we arrive early,
    # stay at the station radius until service_start.
    d = min((ts - trip.unload_at) * speed, route_s)
    if d >= route_s - 1e-6:
        return {"lat": home.lat, "lon": home.lon, "speed_kmh": 0.0}
    p = interpolate(unload, home, d)
    return {"lat": p.lat, "lon": p.lon, "speed_kmh": 36.0}


async def run(config_path, speedup, duplicate_rate, late_rate):
    from aiokafka import AIOKafkaProducer
    cfg = load_config(config_path)
    producer = AIOKafkaProducer(bootstrap_servers=cfg.kafka_bootstrap)
    await producer.start()
    try:
        start = int(time.time())
        schedules = build_schedule(cfg, start)
        cycle = 0
        while True:
            ts = start + cycle
            for unit in cfg.units.values():
                data = telemetry_for(unit, ts, cfg, schedules[unit.uuid])
                payload = {"unit_uuid": unit.uuid, "ts": ts, **data}
                await producer.send_and_wait(cfg.telemetry_topic, key=unit.uuid.encode(), value=json.dumps(payload).encode())

                if random.random() < duplicate_rate:
                    await producer.send_and_wait(cfg.telemetry_topic, key=unit.uuid.encode(), value=json.dumps(payload).encode())
                if random.random() < late_rate and cycle > 60:
                    late = dict(payload)
                    late["ts"] -= random.randint(1, 60)
                    await producer.send_and_wait(cfg.telemetry_topic, key=unit.uuid.encode(), value=json.dumps(late).encode())

            cycle += 1
            await asyncio.sleep(1.0 / speedup)
    finally:
        await producer.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--speedup", type=float, default=1)
    parser.add_argument("--duplicate-rate", type=float, default=0.01)
    parser.add_argument("--late-rate", type=float, default=0.01)
    args = parser.parse_args()
    asyncio.run(run(args.config, args.speedup, args.duplicate_rate, args.late_rate))
