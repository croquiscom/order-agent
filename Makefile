.PHONY: help setup doctor doctor-quiet doctor-json doctor-strict test

help:
	@echo "Available targets:"
	@echo "  make setup         # create .env if needed and run onboarding checks"
	@echo "  make doctor        # run doctor text report"
	@echo "  make doctor-quiet  # show only WARN/FAIL items"
	@echo "  make doctor-json   # write JSON doctor report to logs/doctor.json"
	@echo "  make doctor-strict # fail on WARN or FAIL"
	@echo "  make test          # run unit tests"

setup:
	./scripts/setup_env.sh

doctor:
	./scripts/doctor.sh

doctor-quiet:
	python3 executor/doctor.py --quiet

doctor-json:
	python3 executor/doctor.py --json --output logs/doctor.json

doctor-strict:
	./scripts/setup_env.sh --strict

test:
	python3 -m pytest -q
