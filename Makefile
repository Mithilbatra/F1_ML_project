# Pit Wall — common entry points. `make serve` is all a new user needs.

.PHONY: serve setup test lint docker docker-run backtest

serve:            ## run the dashboard (self-builds data on first run)
	uv run --extra vision f1ml serve

setup:            ## build features + train models from the bundled data
	uv run f1ml setup

test:             ## run the test suite
	uv run --extra vision python -m pytest -q

docker:           ## build the Docker image
	docker build -t pitwall .

docker-run:       ## run the Docker image on http://localhost:5173
	docker run --rm -p 5173:5173 pitwall

backtest:         ## refresh walk-forward backtests for both seasons
	uv run f1ml backtest --year 2025 && uv run f1ml backtest --year 2024
