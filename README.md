# Virtual Queues

Тестовое задание: восстановление виртуальных очередей по телеметрии Kafka и выдача рекомендаций по выбору станции.

## Что реализовано

- непрерывное чтение `telemetry.v1` из Kafka;
- обработка только в event time;
- дедупликация и защита от out-of-order по `unit_uuid + ts`;
- определение состояний машины;
- расчёт ETA с постоянной скоростью 36 км/ч;
- виртуальные очереди на 30 минут;
- исключение stale-позиций старше 30 секунд;
- публикация `queue.v1` только при изменении snapshot;
- одно решение на вход в радиус 1500 м;
- выбор станции по минимальному ожиданию;
- порог выигрыша 60 секунд;
- симулятор 40 машин;
- тесты бизнес-логики без Kafka.

## Важное допущение

ТЗ одновременно говорит, что машина в радиусе станции при занятой станции ждёт, и что ETA для `к станции` считается по геометрической позиции. В реализации при входе в радиус занятой станции машина получает ETA, равную времени входа в радиус через сохранённое состояние/текущую позицию; последующие пересчёты используют свежую позицию.

Для небольшого задания состояние процессора сделано в памяти. Это сознательное упрощение: production-вариант должен использовать Kafka-backed state/changelog или внешний state store.

## Запуск

Требуется Python 3.11+ и Docker.

```bash
docker compose up -d
# kafka-init creates telemetry.v1 (1), queue.v1 (4), decision.v1 (4)
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Запуск процессора:

```bash
python -m app.processor
```

В другом терминале:

```bash
python -m simulator.simulator --speedup 20 --duplicate-rate 0.02 --late-rate 0.02
```

## Топики

- `telemetry.v1` — key `unit_uuid`
- `queue.v1` — key `station_uuid`
- `decision.v1` — key `unit_uuid`

## Kafka partitioning

`docker compose` запускает одно-node Kafka и init-контейнер, который создаёт `telemetry.v1` с 1 partition, `queue.v1` с 4 и `decision.v1` с 4. Для локального теста replication factor равен 1.

## Что сознательно не сделано

- persistent state store;
- distributed repartitioning;
- schema registry;
- production observability;
- exactly-once state recovery.

Причина — объём тестового задания. Бизнес-логика отделена от Kafka и покрыта unit-тестами.

## Затраченное время

Ориентировочно 6–8 часов на реализацию, тестирование и документацию.
