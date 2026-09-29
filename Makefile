test:
	python -m pytest

processor:
	python -m app.processor

simulator:
	python -m simulator.simulator --speedup 20 --duplicate-rate 0.02 --late-rate 0.02

up:
	docker compose up -d

down:
	docker compose down
