# claude --worktree branch-name # open claude session in a worktree

build:
	docker-compose build

up:
	docker-compose down
	docker-compose up
# app available at http://localhost:8501

down:
	docker-compose down

logs:
	docker-compose logs -f app

shell:
	docker-compose exec app /bin/bash

db:
	docker-compose exec postgres psql -U jobrag -d jobrag_db
# SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';

migrate:
	docker-compose exec app poetry run python -m alembic upgrade head

init-db:
	docker-compose exec app poetry run python scripts/init_db.py

db-clear:
	docker-compose exec -T postgres psql -U jobrag -d jobrag_db -c "TRUNCATE jobs, requirements, evidence_matches, edit_packs CASCADE;"

test:
	poetry run pytest

test-job:
	docker-compose exec app poetry run python scripts/test_job_fetch.py

clean:
	docker-compose down -v
	docker-compose rm -f
