#!/usr/bin/env bash
set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:9092}"
BIN="/opt/bitnami/kafka/bin/kafka-topics.sh"

until "$BIN" --bootstrap-server "$BOOTSTRAP" --list >/dev/null 2>&1; do
  sleep 1
done

"$BIN" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic telemetry.v1 --partitions 1 --replication-factor 1
"$BIN" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic queue.v1 --partitions 4 --replication-factor 1
"$BIN" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic decision.v1 --partitions 4 --replication-factor 1
