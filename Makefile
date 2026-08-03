SHELL := /usr/bin/env bash

PYTHON ?= python3
BOOTSTRAP_VENV ?= .venv-bootstrap
BOOTSTRAP_PYTHON := $(BOOTSTRAP_VENV)/bin/python
BOOTSTRAP_PIP := $(BOOTSTRAP_PYTHON) -m pip
SERVICEFABRIC_DOCTOR := $(BOOTSTRAP_VENV)/bin/servicefabric

DAY0_VENV ?= $(CURDIR)/.venv-day0
DAY0_PYTHON := $(DAY0_VENV)/bin/python
DAY0_PACKAGE_PATHS := $(CURDIR)/packages/risk_domain/src:$(CURDIR)/packages/risk_planning/src:$(CURDIR)/packages/risk_data/src:$(CURDIR)/packages/risk_capabilities/src:$(CURDIR)/packages/risk_agents/src:$(CURDIR)/packages/risk_analytics/src:$(CURDIR)/packages/risk_registry/src
DAY0_PYTEST := PYTHONPATH="$(CURDIR):$(DAY0_PACKAGE_PATHS)" $(DAY0_PYTHON) -m pytest
HISTORICAL_JOURNEY_TESTS := $(filter-out tests/journeys/test_thesis%.py,$(wildcard tests/journeys/*.py))
DAY1_VENV ?= $(CURDIR)/.venv-day1
ifeq ($(strip $(DAY1_VENV)),)
override DAY1_VENV := $(CURDIR)/.venv-day1
endif
DAY1_PYTHON := $(DAY1_VENV)/bin/python
DAY1_PACKAGE_PATHS := $(DAY0_PACKAGE_PATHS)
DAY1_PYTEST := PYTHONPATH="$(CURDIR):$(DAY1_PACKAGE_PATHS)" $(DAY1_PYTHON) -m pytest
DAY0_STATE_ROOT := $(abspath $(CURDIR)/../../../state/day0/integration)
PORTFOLIO_RISK_DATA_ROOT := $(DAY0_STATE_ROOT)/portfolio-risk-data
SERVICEFABRIC_RUNTIME_VENV := $(abspath $(CURDIR)/../../../state/venvs/day0/servicefabric-runtime)
SERVICEFABRIC_HOME := $(DAY0_STATE_ROOT)/servicefabric-home-day0-immutable
DAY1_STATE_ROOT := $(abspath $(CURDIR)/../../../state/day1/integration)
DAY1_PORTFOLIO_RISK_DATA_ROOT ?= $(DAY1_STATE_ROOT)/portfolio-risk-data
DAY1_SERVICEFABRIC_RUNTIME_VENV ?= $(abspath $(CURDIR)/../../../state/venvs/day1/servicefabric-runtime)
DAY1_SERVICEFABRIC_HOME ?= $(DAY1_STATE_ROOT)/servicefabric-home-day1

.PHONY: env-check
env-check:
	./scripts/bootstrap/check_environment.sh

.PHONY: repo-check
repo-check:
	./scripts/bootstrap/check_repository.sh

.PHONY: bootstrap-venv
bootstrap-venv:
	test -x "$(BOOTSTRAP_PYTHON)" || $(PYTHON) -m venv "$(BOOTSTRAP_VENV)"
	$(BOOTSTRAP_PIP) install setuptools==80.9.0 wheel==0.45.1
	$(BOOTSTRAP_PIP) install --no-build-isolation -e vendor/servicefabric/packages/servicefabric_release_readiness

.PHONY: upstream-doctor
upstream-doctor: bootstrap-venv
	$(SERVICEFABRIC_DOCTOR) doctor --repository-root vendor/servicefabric

.PHONY: preflight
preflight: env-check repo-check upstream-doctor
	git diff --check
	@echo "Day 0 preparation preflight: PASS"

.PHONY: clean-bootstrap
clean-bootstrap:
	rm -rf "$(BOOTSTRAP_VENV)"

.PHONY: day0-env
day0-env:
	test -f requirements/day0.lock || { \
	  echo "ERROR: requirements/day0.lock is missing" >&2; \
	  exit 1; \
	}
	DAY0_VENV="$(DAY0_VENV)" ./scripts/day0/bootstrap_environment.sh
	test -x "$(DAY0_PYTHON)" || { \
	  echo "ERROR: Day 0 Python was not created at $(DAY0_PYTHON)" >&2; \
	  exit 1; \
	}
	$(DAY0_PYTHON) -m pip check

.PHONY: test-architecture
test-architecture: day0-env
	$(DAY0_PYTEST) tests/architecture -q

.PHONY: test-domain
test-domain: day0-env
	$(DAY0_PYTEST) tests/contracts tests/domain -q

.PHONY: test-planning
test-planning: day0-env
	$(DAY0_PYTEST) tests/planning -q

.PHONY: test-data
test-data: day0-env
	$(DAY0_PYTEST) tests/data -q

.PHONY: test-capabilities
test-capabilities: day0-env
	$(DAY0_PYTEST) tests/capabilities -q

.PHONY: test-agents
test-agents: day0-env
	$(DAY0_PYTEST) tests/agents -q

.PHONY: test-application
test-application: day0-env
	$(DAY0_PYTEST) tests/application -q

.PHONY: test-integration
test-integration: day0-env
	$(DAY0_PYTEST) tests/integration -q

.PHONY: test-journeys
test-journeys: day0-env
	$(DAY0_PYTEST) $(HISTORICAL_JOURNEY_TESTS) -q

.PHONY: verify-wave-0a
verify-wave-0a: test-architecture test-integration
	git diff --check
	@echo "D0-WAVE-0A verification: PASS"

.PHONY: verify-wave-0b
verify-wave-0b: \
  preflight \
  test-architecture \
  test-domain \
  test-planning \
  test-data \
  test-capabilities \
  test-agents \
  test-application \
  test-integration
	git diff --check
	@echo "D0-WAVE-0B verification: PASS"

.PHONY: verify-wave-0c
verify-wave-0c: verify-wave-0b test-journeys
	git diff --check
	@echo "D0-WAVE-0C verification: PASS"

.PHONY: verify-day0
verify-day0: \
  preflight \
  test-architecture \
  test-domain \
  test-planning \
  test-data \
  test-capabilities \
  test-agents \
  test-application \
  test-integration \
  test-journeys
	python3 scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check
	git diff --check
	@echo "Day 0 verification: PASS"

.PHONY: demo-day0-headless
demo-day0-headless: day0-env
	PORTFOLIO_RISK_DATA_ROOT="$(PORTFOLIO_RISK_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(DAY0_PACKAGE_PATHS)" $(DAY0_PYTHON) scripts/day0/run_monitoring_demo.py

.PHONY: servicefabric-smoke
servicefabric-smoke:
	SERVICEFABRIC_RUNTIME_VENV="$(SERVICEFABRIC_RUNTIME_VENV)" \
	SERVICEFABRIC_HOME="$(SERVICEFABRIC_HOME)" \
	PORTFOLIO_RISK_DATA_ROOT="$(PORTFOLIO_RISK_DATA_ROOT)" \
	./scripts/day0/servicefabric_smoke.sh

.PHONY: day1-prep-context
day1-prep-context:
	$(PYTHON) scripts/day1/show_context.py

.PHONY: verify-day1-prep
verify-day1-prep: day0-env
	$(PYTHON) scripts/day1/check_preparation.py --require-prepared
	$(DAY0_PYTEST) tests/architecture/test_day1_preparation.py -q
	$(MAKE) repo-check
	$(MAKE) test-architecture
	$(PYTHON) scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check
	git diff --check
	@echo "Day 1 preparation verification: PASS"

.PHONY: day1-env
day1-env:
	test -f requirements/day1.lock || { echo "ERROR: requirements/day1.lock is missing" >&2; exit 1; }
	DAY1_VENV="$(DAY1_VENV)" ./scripts/day1/bootstrap_environment.sh
	test -x "$(DAY1_PYTHON)" || { echo "ERROR: Day 1 Python was not created at $(DAY1_PYTHON)" >&2; exit 1; }
	$(DAY1_PYTHON) -m pip check

.PHONY: test-day1-architecture
test-day1-architecture: day1-env
	$(DAY1_PYTEST) tests/architecture/test_day1_preparation.py tests/architecture/test_day1_runtime_boundaries.py -q

.PHONY: test-day1-knowledge
test-day1-knowledge: day1-env
	$(DAY1_PYTEST) tests/planning -q
	if test -d tests/research; then $(DAY1_PYTEST) tests/research -q; else echo "No Day 1 research tests yet"; fi

.PHONY: test-day1-experience
test-day1-experience: day1-env
	$(DAY1_PYTEST) tests/application -q

.PHONY: test-day1-data
test-day1-data: day1-env
	$(DAY1_PYTEST) tests/data -q

.PHONY: test-day1-analytics
test-day1-analytics: day1-env
	$(DAY1_PYTEST) tests/contracts tests/domain -q
	if test -d tests/analytics; then $(DAY1_PYTEST) tests/analytics -q; else echo "No Day 1 analytics tests yet"; fi

.PHONY: test-day1-agents
test-day1-agents: day1-env
	$(DAY1_PYTEST) tests/capabilities tests/agents -q

.PHONY: test-day1-integration
test-day1-integration: day1-env
	$(DAY1_PYTEST) tests/integration -q

.PHONY: test-day1-journeys
test-day1-journeys: day1-env
	$(DAY1_PYTEST) $(HISTORICAL_JOURNEY_TESTS) -q

.PHONY: verify-wave-1a
verify-wave-1a: \
  preflight \
  test-architecture \
  test-domain \
  test-planning \
  test-data \
  test-capabilities \
  test-agents \
  test-day1-experience \
  test-day1-integration \
  test-day1-journeys \
  test-day1-knowledge \
  test-day1-architecture
	$(DAY1_PYTHON) scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check
	git diff --check
	@echo "D1-WAVE-1A verification: PASS"

.PHONY: verify-wave-1b
verify-wave-1b: verify-wave-1a test-day1-data test-day1-journeys
	git diff --check
	@echo "D1-WAVE-1B verification: PASS"

.PHONY: verify-wave-1c
verify-wave-1c: verify-wave-1b test-day1-analytics test-day1-agents
	git diff --check
	@echo "D1-WAVE-1C verification: PASS"

.PHONY: verify-day1-current
verify-day1-current: day1-env
	$(DAY1_PYTHON) scripts/day1/verify_current.py

.PHONY: verify-day1
verify-day1: verify-wave-1c test-day1-journeys
	if grep -q "^- ID: D1-" docs/workplans/current.md; then $(DAY1_PYTHON) scripts/day1/check_preparation.py; else echo "Day 1 historical lifecycle is covered by regression tests; a later programme owns the active pointer"; fi
	$(DAY1_PYTHON) scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check
	git diff --check
	@echo "Day 1 verification: PASS"

.PHONY: demo-day1-headless
demo-day1-headless: day1-env
	PORTFOLIO_RISK_DATA_ROOT="$(DAY1_PORTFOLIO_RISK_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(DAY1_PACKAGE_PATHS)" $(DAY1_PYTHON) scripts/day1/run_day1_demo.py

.PHONY: servicefabric-day1-smoke
servicefabric-day1-smoke:
	SERVICEFABRIC_RUNTIME_VENV="$(DAY1_SERVICEFABRIC_RUNTIME_VENV)" \
	SERVICEFABRIC_HOME="$(DAY1_SERVICEFABRIC_HOME)" \
	PORTFOLIO_RISK_DATA_ROOT="$(DAY1_PORTFOLIO_RISK_DATA_ROOT)" \
	./scripts/day1/servicefabric_smoke.sh

DAY23_VENV ?= $(CURDIR)/.venv-day23
ifeq ($(strip $(DAY23_VENV)),)
override DAY23_VENV := $(CURDIR)/.venv-day23
endif
DAY23_PYTHON := $(DAY23_VENV)/bin/python
DAY23_PACKAGE_PATHS := $(DAY0_PACKAGE_PATHS)
DAY23_PYTEST := PYTHONPATH="$(CURDIR):$(DAY23_PACKAGE_PATHS)" $(DAY23_PYTHON) -m pytest
DAY23_STATE_ROOT := $(abspath $(CURDIR)/../../../state/day23/integration)
# Keep the shorter D23_ spelling accepted by the local Day 2–3 shell
# instructions while retaining the documented DAY23_ override.
DAY23_PORTFOLIO_RISK_DATA_ROOT ?= $(if $(D23_PORTFOLIO_RISK_DATA_ROOT),$(D23_PORTFOLIO_RISK_DATA_ROOT),$(DAY23_STATE_ROOT)/portfolio-risk-data)
DAY23_SERVICEFABRIC_RUNTIME_VENV ?= $(abspath $(CURDIR)/../../../state/venvs/day23/servicefabric-runtime)
DAY23_SERVICEFABRIC_HOME ?= $(DAY23_STATE_ROOT)/servicefabric-home-phase1
D23_PART1_HEAD := 0b12e198abc1713f0a286aee817491ffbfe15b17
D23_PART2_HEAD := day23-complete

.PHONY: day23-env
day23-env:
	test -f requirements/day1.lock || { echo "ERROR: requirements/day1.lock is missing" >&2; exit 1; }
	DAY23_VENV="$(DAY23_VENV)" ./scripts/day23/bootstrap_environment.sh
	test -x "$(DAY23_PYTHON)" || { echo "ERROR: Day 2–3 Python was not created at $(DAY23_PYTHON)" >&2; exit 1; }
	$(DAY23_PYTHON) -m pip check

.PHONY: test-d23-control
test-d23-control: day23-env
	$(DAY23_PYTEST) tests/architecture/test_day23_control_plane.py -q

.PHONY: test-d23-data
test-d23-data: day23-env
	$(DAY23_PYTEST) tests/data -q

.PHONY: test-d23-experience
test-d23-experience: day23-env
	$(DAY23_PYTEST) tests/application -q

.PHONY: test-d23-integration
test-d23-integration: day23-env
	$(DAY23_PYTEST) tests/integration -q

.PHONY: test-d23-journeys
test-d23-journeys: day23-env
	$(DAY23_PYTEST) $(HISTORICAL_JOURNEY_TESTS) -q

.PHONY: verify-d23-phase1
verify-d23-phase1: day23-env verify-day1 verify-day0 test-d23-control test-d23-data test-d23-experience test-d23-integration test-d23-journeys
	$(PYTHON) scripts/day23/check_lane_paths.py --all-lanes --base day1-complete --head $(D23_PART1_HEAD) --manifest config/agent/day23/part1-lanes.json
	git diff --check
	@echo "D23 Phase 1 verification: PASS"

.PHONY: demo-d23-phase1
demo-d23-phase1: day23-env
	PORTFOLIO_RISK_DATA_ROOT="$(DAY23_PORTFOLIO_RISK_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(DAY23_PACKAGE_PATHS)" $(DAY23_PYTHON) scripts/day23/run_phase1_demo.py

.PHONY: servicefabric-d23-phase1-smoke
servicefabric-d23-phase1-smoke: demo-d23-phase1
	DAY23_SERVICEFABRIC_RUNTIME_VENV="$(DAY23_SERVICEFABRIC_RUNTIME_VENV)" \
	DAY23_SERVICEFABRIC_HOME="$(DAY23_SERVICEFABRIC_HOME)" \
	PORTFOLIO_RISK_DATA_ROOT="$(DAY23_PORTFOLIO_RISK_DATA_ROOT)" \
	./scripts/day23/servicefabric_phase1_smoke.sh

.PHONY: test-d23-monitoring-core
test-d23-monitoring-core: day23-env
	$(DAY23_PYTEST) tests/contracts tests/domain tests/data tests/analytics tests/capabilities tests/agents -q

.PHONY: test-d23-monitoring-experience
test-d23-monitoring-experience: day23-env
	$(DAY23_PYTEST) tests/application -q

.PHONY: test-d23-part2-integration
test-d23-part2-integration: day23-env
	$(DAY23_PYTEST) tests/integration -q

.PHONY: test-d23-part2-journeys
test-d23-part2-journeys: day23-env
	$(DAY23_PYTEST) $(HISTORICAL_JOURNEY_TESTS) -q

.PHONY: check-d23-application-manifest
check-d23-application-manifest: day23-env
	$(DAY23_PYTHON) scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check

.PHONY: verify-d23-part2
verify-d23-part2: verify-d23-phase1 test-d23-monitoring-core test-d23-monitoring-experience test-d23-part2-integration test-d23-part2-journeys check-d23-application-manifest
	$(PYTHON) scripts/day23/check_lane_paths.py --all-lanes --base $(D23_PART1_HEAD) --head $(D23_PART2_HEAD) --manifest config/agent/day23/lanes.json
	git diff --check
	@echo "D23 Part 2 verification: PASS"

.PHONY: verify-d23-current
verify-d23-current: verify-d23-part2
	@echo "D23 current verification: PASS"

.PHONY: demo-d23-part2
demo-d23-part2: day23-env
	PORTFOLIO_RISK_DATA_ROOT="$(DAY23_PORTFOLIO_RISK_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(DAY23_PACKAGE_PATHS)" $(DAY23_PYTHON) scripts/day23/run_part2_demo.py

.PHONY: servicefabric-d23-part2-smoke
servicefabric-d23-part2-smoke: demo-d23-part2
	DAY23_SERVICEFABRIC_RUNTIME_VENV="$(DAY23_SERVICEFABRIC_RUNTIME_VENV)" \
	DAY23_SERVICEFABRIC_HOME="$(DAY23_SERVICEFABRIC_HOME)" \
	PORTFOLIO_RISK_DATA_ROOT="$(DAY23_PORTFOLIO_RISK_DATA_ROOT)" \
	./scripts/day23/servicefabric_part2_smoke.sh

THESIS_VENV ?= $(CURDIR)/.venv-thesis
ifeq ($(strip $(THESIS_VENV)),)
override THESIS_VENV := $(CURDIR)/.venv-thesis
endif
THESIS_PYTHON := $(THESIS_VENV)/bin/python
THESIS_PACKAGE_PATHS := $(CURDIR)/packages/risk_domain/src:$(CURDIR)/packages/risk_planning/src:$(CURDIR)/packages/risk_data/src:$(CURDIR)/packages/risk_capabilities/src:$(CURDIR)/packages/risk_agents/src:$(CURDIR)/packages/risk_analytics/src:$(CURDIR)/packages/risk_registry/src:$(CURDIR)/examples/portfolio-risk-thesis/src
THESIS_PYTEST := PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m pytest
THESIS_STATE_ROOT := $(abspath $(CURDIR)/../../../state/thesis-sprint/integration)
THESIS_DATA_ROOT ?= $(THESIS_STATE_ROOT)/data
THESIS_INTEGRATION_TESTS := $(wildcard tests/integration/test_thesis*.py)
THESIS_JOURNEY_TESTS := $(wildcard tests/journeys/test_thesis*.py)
THESIS_FIXTURE_VALIDATOR := examples/portfolio-risk-thesis/scripts/validate_fixture_digests.py
THESIS_DEMO := scripts/thesis/run_day1_demo.py
THESIS_DAY1_LANE_BASE ?= $(shell git log --diff-filter=A --format=%H -1 -- config/agent/thesis-sprint/status.json 2>/dev/null)
THESIS_DAY1_CANDIDATE_HEAD := 433ee994998afd3c7e79cd1169ddcdd24e19960f
THESIS_DAY1_LANE_HEAD ?= $(THESIS_DAY1_CANDIDATE_HEAD)

.PHONY: thesis-env
thesis-env:
	test -f requirements/thesis.lock || { echo "ERROR: requirements/thesis.lock is missing" >&2; exit 1; }
	THESIS_VENV="$(THESIS_VENV)" ./scripts/thesis/bootstrap_environment.sh
	test -x "$(THESIS_PYTHON)" || { echo "ERROR: Thesis Python was not created at $(THESIS_PYTHON)" >&2; exit 1; }
	$(THESIS_PYTHON) -m pip check

.PHONY: test-thesis-control
test-thesis-control: thesis-env
	$(THESIS_PYTEST) tests/architecture/test_thesis_sprint_control_plane.py -q

.PHONY: test-thesis-day1
test-thesis-day1: thesis-env
	if test -d tests/thesis; then $(THESIS_PYTEST) tests/thesis -q; else echo "No Thesis Sprint Day 1 implementation tests yet"; fi

.PHONY: test-thesis-integration
test-thesis-integration: thesis-env
	if test -n "$(strip $(THESIS_INTEGRATION_TESTS))"; then $(THESIS_PYTEST) $(THESIS_INTEGRATION_TESTS) -q; else echo "No Thesis Sprint integration tests yet"; fi

.PHONY: test-thesis-journeys
test-thesis-journeys: thesis-env
	if test -n "$(strip $(THESIS_JOURNEY_TESTS))"; then $(THESIS_PYTEST) $(THESIS_JOURNEY_TESTS) -q; else echo "No Thesis Sprint journey tests yet"; fi

.PHONY: check-thesis-day1-fixture-digests
check-thesis-day1-fixture-digests: thesis-env
	test -f "$(THESIS_FIXTURE_VALIDATOR)" || { echo "ERROR: Day 1 fixture digest validator is not implemented" >&2; exit 1; }
	test -d data/fixtures/synthetic/thesis-day1 || { echo "ERROR: Day 1 synthetic fixtures are not implemented" >&2; exit 1; }
	THESIS_DATA_ROOT="$(THESIS_DATA_ROOT)" $(THESIS_PYTHON) "$(THESIS_FIXTURE_VALIDATOR)" --fixtures data/fixtures/synthetic/thesis-day1

.PHONY: verify-thesis-day1
verify-thesis-day1: \
  verify-d23-current \
  test-thesis-control \
  test-thesis-day1 \
  test-thesis-integration \
  test-thesis-journeys \
  check-thesis-day1-fixture-digests
	@if grep -q "^- ID: THESIS-" docs/workplans/current.md; then \
	  test -n "$(THESIS_DAY1_LANE_BASE)" || { echo "ERROR: unable to resolve the Thesis Sprint control-plane commit" >&2; exit 1; }; \
	  git merge-base --is-ancestor "$(THESIS_DAY1_LANE_BASE)" "$(THESIS_DAY1_LANE_HEAD)" || { echo "ERROR: specialist candidate must descend from the Thesis Sprint control-plane commit" >&2; exit 1; }; \
	  $(THESIS_PYTHON) scripts/thesis/check_lane_paths.py --lane day1 --base "$(THESIS_DAY1_LANE_BASE)" --head "$(THESIS_DAY1_LANE_HEAD)" --manifest config/agent/thesis-sprint/lanes.json; \
	else \
	  echo "Thesis Day 1 lane ownership is historical; a later programme owns the active pointer"; \
	fi
	git diff --check
	@echo "Thesis Sprint Day 1 verification: PASS"

.PHONY: test-thesis-day3
test-thesis-day3: thesis-env
	$(THESIS_PYTEST) tests/thesis/test_day3_contracts.py tests/thesis/test_day3_context.py tests/thesis/test_day3_events.py tests/thesis/test_day3_provider.py tests/thesis/test_day3_critic.py tests/thesis/test_day3_treatments.py tests/thesis/test_day3_runner.py tests/journeys/test_thesis_day3_vertical_slice.py -q

.PHONY: test-thesis-day3-boundaries
test-thesis-day3-boundaries: thesis-env
	$(THESIS_PYTEST) tests/architecture/test_thesis_day3_boundaries.py -q

.PHONY: test-thesis-day3-provider test-thesis-day3-critic test-thesis-day3-architectures
test-thesis-day3-provider: thesis-env
	$(THESIS_PYTEST) tests/thesis/test_day3_provider.py -q

test-thesis-day3-critic: thesis-env
	$(THESIS_PYTEST) tests/thesis/test_day3_critic.py -q

test-thesis-day3-architectures: thesis-env
	$(THESIS_PYTEST) tests/thesis/test_day3_treatments.py tests/thesis/test_day3_runner.py tests/journeys/test_thesis_day3_vertical_slice.py -q

.PHONY: verify-thesis-day3
verify-thesis-day3: verify-thesis-day2 test-thesis-day3-boundaries test-thesis-day3
	git diff --check
	@echo "Thesis Sprint Day 3 fixture verification: PASS"

.PHONY: demo-thesis-day3-fixture
demo-thesis-day3-fixture: thesis-env
	test -n "$(THESIS_DATA_ROOT)" || { echo "ERROR: set THESIS_DATA_ROOT" >&2; exit 1; }
	case "$(abspath $(THESIS_DATA_ROOT))" in "$(CURDIR)"|"$(CURDIR)"/*) echo "ERROR: THESIS_DATA_ROOT must remain outside Git" >&2; exit 1;; esac
	mkdir -p "$(THESIS_DATA_ROOT)"
	THESIS_DATA_ROOT="$(THESIS_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) scripts/thesis/run_day3_demo.py

.PHONY: complete-thesis-day3-interactive
complete-thesis-day3-interactive: thesis-env
	THESIS_VENV="$(THESIS_VENV)" ./scripts/thesis/complete_day3_interactive.sh

.PHONY: run-thesis-day3-direct
run-thesis-day3-direct: thesis-env
	THESIS_VENV="$(THESIS_VENV)" ./scripts/thesis/run_day3_direct.sh

.PHONY: verify-thesis-day3-real
verify-thesis-day3-real: verify-thesis-day3
	@test -n "$(THESIS_REAL_EXPERIMENT_MANIFEST)" || { echo "ERROR: set THESIS_REAL_EXPERIMENT_MANIFEST" >&2; exit 1; }
	@test -n "$(THESIS_DAY2_RUN_DIR)" || { echo "ERROR: set THESIS_DAY2_RUN_DIR" >&2; exit 1; }
	@test -n "$(THESIS_DAY3_EVENT_MANIFEST)" || { echo "ERROR: set THESIS_DAY3_EVENT_MANIFEST" >&2; exit 1; }
	@test -n "$(THESIS_DAY3_EVENT_DATASET)" || { echo "ERROR: set THESIS_DAY3_EVENT_DATASET" >&2; exit 1; }
	@test -n "$(THESIS_DAY3_MODEL_CONFIG)" || { echo "ERROR: set THESIS_DAY3_MODEL_CONFIG" >&2; exit 1; }
	@test -n "$(THESIS_DAY3_EXPERIMENT_MANIFEST)" || { echo "ERROR: set THESIS_DAY3_EXPERIMENT_MANIFEST" >&2; exit 1; }
	@test -n "$(THESIS_DAY3_OUTPUT_ROOT)" || { echo "ERROR: set THESIS_DAY3_OUTPUT_ROOT" >&2; exit 1; }
	@test -n "$(THESIS_DAY3_RUN_DIR)" || { echo "ERROR: set THESIS_DAY3_RUN_DIR" >&2; exit 1; }
	@test -n "$$OPENAI_API_KEY" || { echo "ERROR: OPENAI_API_KEY must be loaded from Keychain" >&2; exit 1; }
	PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m portfolio_risk_thesis.cli validate-day3-events --manifest "$(THESIS_DAY3_EVENT_MANIFEST)" --dataset "$(THESIS_DAY3_EVENT_DATASET)"
	PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m portfolio_risk_thesis.cli validate-day3 --experiment-manifest "$(THESIS_DAY3_EXPERIMENT_MANIFEST)"
	PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m portfolio_risk_thesis.cli validate-day3-run --run-directory "$(THESIS_DAY3_RUN_DIR)" --require-successful-provider
	@echo "Thesis Sprint Day 3 local provider verification: PASS"

.PHONY: demo-thesis-day3-real
demo-thesis-day3-real: verify-thesis-day3-real
	@echo "Day 3 real comparison already exists and passed the immutable local gate."

.PHONY: test-thesis-day4-boundaries
test-thesis-day4-boundaries: thesis-env
	$(THESIS_PYTEST) tests/architecture/test_thesis_day4_boundaries.py -q

THESIS_DAY4_FIXTURE_MANIFEST := examples/portfolio-risk-thesis/experiments/day4_fixture.yaml
THESIS_DAY4_FIXTURE_OUTPUT ?= $(THESIS_DATA_ROOT)/day4-fixture
THESIS_DAY4_EXPERIMENT_MANIFEST ?=
THESIS_DAY4_OUTPUT_ROOT ?=
THESIS_DAY4_RUN_DIR ?=

.PHONY: test-thesis-day4
test-thesis-day4: thesis-env
	$(THESIS_PYTEST) tests/thesis/test_day4_contracts.py tests/thesis/test_day4_manifest.py tests/thesis/test_day4_labels.py tests/thesis/test_day4_evaluation.py tests/thesis/test_day4_runner.py tests/thesis/test_day4_report.py -q

.PHONY: demo-thesis-day4-fixture
demo-thesis-day4-fixture: thesis-env
	test -n "$(THESIS_DATA_ROOT)" || { echo "ERROR: set THESIS_DATA_ROOT" >&2; exit 1; }
	case "$(abspath $(THESIS_DATA_ROOT))" in "$(CURDIR)"|"$(CURDIR)"/*) echo "ERROR: THESIS_DATA_ROOT must remain outside Git" >&2; exit 1;; esac
	mkdir -p "$(THESIS_DAY4_FIXTURE_OUTPUT)"
	THESIS_DATA_ROOT="$(THESIS_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m portfolio_risk_thesis.cli run-day4 --experiment-manifest "$(THESIS_DAY4_FIXTURE_MANIFEST)" --provider fixture --allow-fixture-provider --authorized-model-calls 270 --output-root "$(THESIS_DAY4_FIXTURE_OUTPUT)" --resume
	THESIS_DATA_ROOT="$(THESIS_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m portfolio_risk_thesis.cli validate-day4-run --run-directory "$$(find "$(THESIS_DAY4_FIXTURE_OUTPUT)" -maxdepth 1 -type d -name 'day4_*' | sort | tail -n 1)" --require-successful-provider --require-exit-criteria

.PHONY: verify-thesis-day4
verify-thesis-day4: verify-thesis-day3 test-thesis-day4-boundaries test-thesis-day4 demo-thesis-day4-fixture
	git diff --check
	@echo "Thesis Sprint Day 4 fixture verification: PASS"

.PHONY: verify-thesis-day4-real
verify-thesis-day4-real: verify-thesis-day4
	@test -n "$(THESIS_DAY4_EXPERIMENT_MANIFEST)" || { echo "ERROR: set THESIS_DAY4_EXPERIMENT_MANIFEST" >&2; exit 1; }
	@test -n "$(THESIS_DAY4_OUTPUT_ROOT)" || { echo "ERROR: set THESIS_DAY4_OUTPUT_ROOT" >&2; exit 1; }
	@test -n "$(THESIS_DAY4_RUN_DIR)" || { echo "ERROR: set THESIS_DAY4_RUN_DIR" >&2; exit 1; }
	PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m portfolio_risk_thesis.cli validate-day4 --experiment-manifest "$(THESIS_DAY4_EXPERIMENT_MANIFEST)"
	PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m portfolio_risk_thesis.cli validate-day4-run --run-directory "$(THESIS_DAY4_RUN_DIR)" --require-successful-provider --require-exit-criteria
	@echo "Thesis Sprint Day 4 local provider verification: PASS"

.PHONY: run-thesis-day4-direct
run-thesis-day4-direct: thesis-env
	@test -n "$(THESIS_DAY4_EXPERIMENT_MANIFEST)" || { echo "ERROR: set THESIS_DAY4_EXPERIMENT_MANIFEST" >&2; exit 1; }
	@test -n "$(THESIS_DAY4_OUTPUT_ROOT)" || { echo "ERROR: set THESIS_DAY4_OUTPUT_ROOT" >&2; exit 1; }
	@test -n "$$OPENAI_API_KEY" || { echo "ERROR: OPENAI_API_KEY must be loaded explicitly" >&2; exit 1; }
	THESIS_DATA_ROOT="$(THESIS_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m portfolio_risk_thesis.cli run-day4 --experiment-manifest "$(THESIS_DAY4_EXPERIMENT_MANIFEST)" --provider openai_responses --authorized-model-calls 270 --output-root "$(THESIS_DAY4_OUTPUT_ROOT)" --resume

.PHONY: serve-thesis-day4-dashboard
serve-thesis-day4-dashboard:
	@test -n "$(THESIS_DAY4_RUN_DIR)" || { echo "ERROR: set THESIS_DAY4_RUN_DIR" >&2; exit 1; }
	@test -f "$(THESIS_DAY4_RUN_DIR)/dashboard/index.html" || { echo "ERROR: dashboard is missing" >&2; exit 1; }
	cd "$(THESIS_DAY4_RUN_DIR)/dashboard" && "$(THESIS_PYTHON)" -m http.server 8765 --bind 127.0.0.1

.PHONY: verify-thesis-current
verify-thesis-current: verify-thesis-day4
	@echo "Thesis Sprint current verification: PASS (Day 3 complete; Day 4 public fixture verified; real panel and human QA deferred)"

# Day 2 real-data targets execute the accepted local bridge. All licensed
# inputs and outputs remain external and are supplied explicitly by the user.
THESIS_REAL_DATA_ROOT ?=
THESIS_REAL_SOURCE_SCHEMAS ?=
THESIS_REAL_MANIFEST ?=
THESIS_REAL_PROFILE_OUTPUT ?=
THESIS_REAL_DSF ?=
THESIS_REAL_MSF ?=
THESIS_REAL_CANDIDATE_ARTIFACT ?=
THESIS_REAL_PORTFOLIO_SELECTION ?=
THESIS_REAL_PORTFOLIO_OUTPUT ?=
THESIS_REAL_PORTFOLIO_DIRECTORY ?=
THESIS_REAL_SOURCE_MANIFEST ?=
THESIS_REAL_EXPERIMENT_MANIFEST ?=
THESIS_REAL_OUTPUT_ROOT ?=
THESIS_DAY2_OUTPUT_ROOT ?=
THESIS_DAY2_DEMO := scripts/thesis/run_day2_demo.py

.PHONY: test-thesis-real-data
test-thesis-real-data: thesis-env
	$(THESIS_PYTEST) tests/architecture/test_thesis_real_data_boundaries.py tests/data/test_thesis_crsp_compustat_bridge.py tests/thesis/test_day2_adapter_profiles.py -q

.PHONY: profile-thesis-real-data
profile-thesis-real-data:
	@real_root='$(strip $(THESIS_REAL_DATA_ROOT))'; schema_file='$(strip $(THESIS_REAL_SOURCE_SCHEMAS))'; manifest='$(strip $(THESIS_REAL_MANIFEST))'; \
  test -n "$$real_root" || { echo "ERROR: set THESIS_REAL_DATA_ROOT to an external private directory" >&2; exit 1; }; \
  test -n "$$schema_file" || { echo "ERROR: set THESIS_REAL_SOURCE_SCHEMAS explicitly" >&2; exit 1; }; \
  case "$$real_root" in /*) ;; *) echo "ERROR: THESIS_REAL_DATA_ROOT must be absolute" >&2; exit 1;; esac; \
  case "$$schema_file" in /*) ;; *) echo "ERROR: THESIS_REAL_SOURCE_SCHEMAS must be absolute" >&2; exit 1;; esac; \
  test -n "$$manifest" || { echo "ERROR: set THESIS_REAL_MANIFEST explicitly" >&2; exit 1; }; \
  test -n "$(strip $(THESIS_REAL_PROFILE_OUTPUT))" || { echo "ERROR: set THESIS_REAL_PROFILE_OUTPUT explicitly" >&2; exit 1; }; \
  case "$$manifest" in /*) ;; *) echo "ERROR: THESIS_REAL_MANIFEST must be absolute" >&2; exit 1;; esac; \
  test -d "$$real_root" || { echo "ERROR: THESIS_REAL_DATA_ROOT must be an existing directory" >&2; exit 1; }; \
  test -f "$$schema_file" || { echo "ERROR: source-schemas.json is required" >&2; exit 1; }; \
  test "$${schema_file##*/}" = "source-schemas.json" || { echo "ERROR: schema path must name source-schemas.json" >&2; exit 1; }; \
  repository_root=$$(realpath -- "$(CURDIR)") || exit 1; \
  real_root=$$(realpath -- "$$real_root") || exit 1; \
  schema_file=$$(realpath -- "$$schema_file") || exit 1; \
  manifest=$$(realpath -- "$$manifest") || exit 1; \
  case "$$real_root" in "$$repository_root"|"$$repository_root"/*) echo "ERROR: THESIS_REAL_DATA_ROOT must remain outside Git" >&2; exit 1;; esac; \
  case "$$schema_file" in "$$repository_root"|"$$repository_root"/*) echo "ERROR: THESIS_REAL_SOURCE_SCHEMAS must remain outside Git" >&2; exit 1;; esac; \
  case "$$manifest" in "$$repository_root"|"$$repository_root"/*) echo "ERROR: THESIS_REAL_MANIFEST must remain outside Git" >&2; exit 1;; esac; \
  test -f "$$manifest" || { echo "ERROR: THESIS_REAL_MANIFEST must exist" >&2; exit 1; }
	$(THESIS_PYTHON) -m risk_data.cli profile-crsp-compustat --manifest "$(THESIS_REAL_MANIFEST)" --output "$(THESIS_REAL_PROFILE_OUTPUT)"

.PHONY: build-thesis-real-data
build-thesis-real-data: profile-thesis-real-data
	test -n "$(THESIS_REAL_DATA_ROOT)" || { echo "ERROR: set THESIS_REAL_DATA_ROOT explicitly" >&2; exit 1; }
	$(THESIS_PYTHON) -m risk_data.cli build-crsp-compustat --manifest "$(THESIS_REAL_MANIFEST)" --data-root "$(THESIS_REAL_DATA_ROOT)" --mode daily-primary

.PHONY: verify-thesis-real-data
verify-thesis-real-data: test-thesis-real-data build-thesis-real-data
	$(THESIS_PYTHON) -m risk_data.cli verify-crsp-compustat --data-root "$(THESIS_REAL_DATA_ROOT)" --mode daily-primary

.PHONY: verify-thesis-real-data-daily
verify-thesis-real-data-daily:
	@daily_file='$(strip $(THESIS_REAL_DSF))'; \
  test -n "$$daily_file" || { echo "ERROR: daily-primary requires explicit dsf.parquet" >&2; exit 1; }; \
  case "$$daily_file" in /*) ;; *) echo "ERROR: THESIS_REAL_DSF must be absolute" >&2; exit 1;; esac; \
  test "$${daily_file##*/}" = "dsf.parquet" || { echo "ERROR: daily-primary path must name dsf.parquet" >&2; exit 1; }; \
  test -f "$$daily_file" || { echo "ERROR: dsf.parquet not found" >&2; exit 1; }; \
  repository_root=$$(realpath -- "$(CURDIR)") || exit 1; \
  daily_file=$$(realpath -- "$$daily_file") || exit 1; \
  case "$$daily_file" in "$$repository_root"|"$$repository_root"/*) echo "ERROR: THESIS_REAL_DSF must remain outside Git" >&2; exit 1;; esac
	$(MAKE) verify-thesis-real-data THESIS_REAL_DATA_ROOT="$(THESIS_REAL_DATA_ROOT)" THESIS_REAL_MANIFEST="$(THESIS_REAL_MANIFEST)" THESIS_REAL_SOURCE_SCHEMAS="$(THESIS_REAL_SOURCE_SCHEMAS)" THESIS_REAL_PROFILE_OUTPUT="$(THESIS_REAL_PROFILE_OUTPUT)"

.PHONY: test-thesis-real-portfolios
test-thesis-real-portfolios: thesis-env
	$(THESIS_PYTEST) tests/thesis/test_day2_real_portfolios.py -q

.PHONY: materialize-thesis-real-portfolios
materialize-thesis-real-portfolios:
	test -n "$(strip $(THESIS_REAL_CANDIDATE_ARTIFACT))" || { echo "ERROR: set THESIS_REAL_CANDIDATE_ARTIFACT" >&2; exit 1; }
	test -n "$(strip $(THESIS_REAL_PORTFOLIO_SELECTION))" || { echo "ERROR: set THESIS_REAL_PORTFOLIO_SELECTION" >&2; exit 1; }
	test -n "$(strip $(THESIS_REAL_PORTFOLIO_OUTPUT))" || { echo "ERROR: set THESIS_REAL_PORTFOLIO_OUTPUT" >&2; exit 1; }
	$(MAKE) test-thesis-real-portfolios
	THESIS_DATA_ROOT="$(THESIS_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m portfolio_risk_thesis.cli init-real-portfolios --candidate-artifact "$(THESIS_REAL_CANDIDATE_ARTIFACT)" --selection "$(THESIS_REAL_PORTFOLIO_SELECTION)" --output-directory "$(THESIS_REAL_PORTFOLIO_OUTPUT)"

.PHONY: verify-thesis-real-portfolios
verify-thesis-real-portfolios:
	test -n "$(strip $(THESIS_REAL_PORTFOLIO_DIRECTORY))" || { echo "ERROR: set THESIS_REAL_PORTFOLIO_DIRECTORY" >&2; exit 1; }
	$(MAKE) test-thesis-real-portfolios
	THESIS_DATA_ROOT="$(THESIS_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) -m portfolio_risk_thesis.cli validate-real-portfolios --portfolios-directory "$(THESIS_REAL_PORTFOLIO_DIRECTORY)" --receipt "$(THESIS_REAL_PORTFOLIO_DIRECTORY)/portfolio-selection-receipt.json"

.PHONY: test-thesis-day2
test-thesis-day2: thesis-env
	$(THESIS_PYTEST) tests/thesis/test_day2_metrics_kernel.py tests/journeys/test_thesis_day2_vertical_slice.py -q

.PHONY: verify-thesis-day2
verify-thesis-day2: verify-thesis-day1 test-thesis-real-data test-thesis-day2
	git diff --check
	@echo "Thesis Sprint Day 2 synthetic verification: PASS"

.PHONY: verify-thesis-day2-real
verify-thesis-day2-real: verify-thesis-day2 demo-thesis-day2-real
	@echo "Thesis Sprint Day 2 licensed local verification: PASS"

.PHONY: demo-thesis-day2-real
demo-thesis-day2-real: thesis-env
	@test -f "$(THESIS_DAY2_DEMO)" || { echo "ERROR: Day 2 demo is not implemented" >&2; exit 1; }
	@test -n "$(strip $(THESIS_REAL_SOURCE_MANIFEST))" || { echo "ERROR: set THESIS_REAL_SOURCE_MANIFEST" >&2; exit 1; }
	@test -n "$(strip $(THESIS_REAL_EXPERIMENT_MANIFEST))" || { echo "ERROR: set THESIS_REAL_EXPERIMENT_MANIFEST" >&2; exit 1; }
	@test -n "$(strip $(THESIS_REAL_OUTPUT_ROOT))" || { echo "ERROR: set THESIS_REAL_OUTPUT_ROOT" >&2; exit 1; }
	@test -n "$(strip $(THESIS_DAY2_OUTPUT_ROOT))" || { echo "ERROR: set THESIS_DAY2_OUTPUT_ROOT" >&2; exit 1; }
	@PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" \
  THESIS_REAL_SOURCE_MANIFEST="$(THESIS_REAL_SOURCE_MANIFEST)" \
  THESIS_REAL_EXPERIMENT_MANIFEST="$(THESIS_REAL_EXPERIMENT_MANIFEST)" \
  THESIS_REAL_OUTPUT_ROOT="$(THESIS_REAL_OUTPUT_ROOT)" \
  THESIS_DAY2_OUTPUT_ROOT="$(THESIS_DAY2_OUTPUT_ROOT)" \
  $(THESIS_PYTHON) "$(THESIS_DAY2_DEMO)"

.PHONY: demo-thesis-day1
demo-thesis-day1: thesis-env
	test -f "$(THESIS_DEMO)" || { echo "ERROR: Day 1 demo is not implemented" >&2; exit 1; }
	case "$(abspath $(THESIS_DATA_ROOT))" in "$(CURDIR)"|"$(CURDIR)"/*) echo "ERROR: THESIS_DATA_ROOT must remain outside Git" >&2; exit 1;; esac
	mkdir -p "$(THESIS_DATA_ROOT)"
	THESIS_DATA_ROOT="$(THESIS_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(THESIS_PACKAGE_PATHS)" $(THESIS_PYTHON) "$(THESIS_DEMO)" --data-root "$(THESIS_DATA_ROOT)"

.PHONY: verify-platform-phase0
verify-platform-phase0: preflight day0-env
	$(DAY0_PYTEST) tests/architecture/test_platform_development_control_plane.py tests/architecture/test_thesis_sprint_control_plane.py -q
	git diff --check
	@echo "Platform development Phase 0 control plane: PASS"

.PHONY: verify-platform-phase1
verify-platform-phase1: preflight day0-env
	$(DAY0_PYTEST) tests/architecture/test_platform_phase1_control_plane.py tests/registry tests/application/test_registry_api.py -q
	git diff --check
	@echo "Platform development Phase 1 registry kernel: PASS"
