.PHONY: help setup doctor doctor-quiet doctor-json doctor-strict test map map-json map-update map-gaps

help:
	@echo "Available targets:"
	@echo "  make setup         # create .env if needed and run onboarding checks"
	@echo "  make doctor        # run doctor text report"
	@echo "  make doctor-quiet  # show only WARN/FAIL items"
	@echo "  make doctor-json   # write JSON doctor report to logs/doctor.json"
	@echo "  make doctor-strict # fail on WARN or FAIL"
	@echo "  make test          # run unit tests"
	@echo "  make map           # 시나리오 커버리지 맵 터미널 리포트"
	@echo "  make map-json      # 시나리오 커버리지 맵 JSON 출력"
	@echo "  make map-update    # docs/order_flow_map.md 자동 갱신"
	@echo "  make map-gaps      # 미커버 액션만 표시"

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

map:
	python3 scripts/generate_scenario_map.py

map-json:
	python3 scripts/generate_scenario_map.py --json

map-update:
	python3 scripts/generate_scenario_map.py --update-doc

map-gaps:
	python3 scripts/generate_scenario_map.py --gaps-only
