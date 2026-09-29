PYTHON ?= python3
ALEMBIC_CONFIG ?= backend/alembic.ini

.PHONY: backend-test frontend-check migration-check db-current db-upgrade db-adopt teaching-smoke verify

backend-test:
	PYTHONPATH=backend $(PYTHON) -m unittest discover -s backend -p 'test_*.py'

frontend-check:
	npm --prefix frontend test
	npm --prefix frontend run lint
	npm --prefix frontend run build

migration-check:
	PYTHONPATH=backend $(PYTHON) -m unittest backend/test_migrations.py

db-current:
	PYTHONPATH=backend $(PYTHON) -m alembic -c $(ALEMBIC_CONFIG) current

db-upgrade:
	PYTHONPATH=backend $(PYTHON) backend/scripts/upgrade_database.py

db-adopt:
	PYTHONPATH=backend $(PYTHON) backend/scripts/adopt_alembic_baseline.py

teaching-smoke:
	mkdir -p .artifacts
	PYTHONPATH=backend $(PYTHON) backend/teaching_accuracy_benchmark.py \
		--profile smoke --strict-oracle --output .artifacts/teaching-smoke.json
	PYTHONPATH=backend $(PYTHON) backend/validate_teaching_report.py \
		.artifacts/teaching-smoke.json

verify: backend-test frontend-check
