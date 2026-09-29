# Architecture

## 1. Сколько процессоров и критерий

Используется один логический processor на одну входную partition.

Критерий: **число процессоров определяется числом входных partition, при этом для текущих 40 машин достаточно одной partition и одного активного processor.**

Это сохраняет весь station state локально и не требует distributed join для решения.

## 2. Ключ процессора и состояние

Kafka key `unit_uuid`.

В состоянии:

- последняя принятая телеметрия каждой машины;
- travel state;
- домашняя станция;
- текущая занятая станция;
- время занятия;
- активная рекомендация;
- состояние четырёх станций;
- последний опубликованный snapshot очереди.

## 3. Телеметрия по машинам, очередь по станциям

Для текущего масштаба все машины обрабатываются одним processor. Поэтому station state доступен синхронно при обработке каждого telemetry event.

При масштабировании первый этап остаётся partitioned по `unit_uuid`, затем поток можно repartition по `station_uuid` для queue aggregation, а решения строить через компактный broadcast/cache station snapshots.

Для тестового задания distributed join сознательно не вводится.

## 4. Partitioning и параллелизм

Текущая конфигурация:

- `telemetry.v1`: 1 partition;
- `queue.v1`: 4 partitions;
- `decision.v1`: 4 partitions.

Входной параллелизм ограничен числом partitions.

Количество output partitions не увеличивает параллелизм расчёта: processor публикует результаты после обновления единого состояния.

Production-вариант можно поднять до N входных partitions при переносе state в Kafka-backed store.

## 5. Delivery guarantees

Producer использует idempotence.

Для `queue.v1` downstream получает snapshots, поэтому повторная доставка одного snapshot не меняет конечное состояние при идемпотентной обработке по ключу/версии.

Для `decision.v1` желательно иметь event id вида:

`unit_uuid + trigger_ts`

и deduplication downstream.

Если требуется строгая exactly-once семантика, consume → state update → produce → offset commit должна быть объединена Kafka transactions.

## 6. Restart

В текущем тестовом варианте состояние находится в памяти, поэтому restart приводит к восстановлению состояния повторным чтением Kafka с `earliest` для consumer group.

Уже опубликованные решения могут быть вычислены повторно. Downstream должен дедуплицировать `unit_uuid + trigger_ts`.

Production-решение: changelog/state store, чтобы восстановление зависело от объёма state, а не от всей истории telemetry.

## 7. Что не вынесено

Не выделены отдельные processors:

- по машинам;
- по станциям;
- для decision engine.

Причина: при 40 машинах и 4 станциях дополнительный network shuffle и distributed coordination усложнили бы решение без выигрыша.

Business logic разделена на:

`StateManager → QueueEngine → DecisionEngine → Kafka adapter`

что позволяет тестировать правила без брокера.
