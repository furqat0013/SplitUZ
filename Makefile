.PHONY: run test import verify fresh clean
run:
	docker compose up --build
test:
	docker compose run --rm app python -m pytest -q
import:
	docker compose run --rm app python -m app.cli import /app/dataset
verify:
	docker compose run --rm app sh -c "python -m app.cli import /app/dataset && python -m app.cli verify /app/dataset/_javob_kaliti/net_balanslar.csv"
fresh:
	docker compose down -v
	docker compose up --build
clean:
	docker compose down
