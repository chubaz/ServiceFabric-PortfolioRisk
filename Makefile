SHELL := /usr/bin/env bash
.RECIPEPREFIX := >

PYTHON ?= python3
BOOTSTRAP_VENV ?= .venv-bootstrap
BOOTSTRAP_PYTHON := $(BOOTSTRAP_VENV)/bin/python
BOOTSTRAP_PIP := $(BOOTSTRAP_PYTHON) -m pip
SERVICEFABRIC_DOCTOR := $(BOOTSTRAP_VENV)/bin/servicefabric

DAY0_VENV ?= $(CURDIR)/.venv-day0
DAY0_PYTHON := $(DAY0_VENV)/bin/python
DAY0_PACKAGE_PATHS := $(CURDIR)/packages/risk_domain/src:$(CURDIR)/packages/risk_planning/src:$(CURDIR)/packages/risk_data/src:$(CURDIR)/packages/risk_capabilities/src:$(CURDIR)/packages/risk_agents/src
DAY0_PYTEST := PYTHONPATH="$(CURDIR):$(DAY0_PACKAGE_PATHS)" $(DAY0_PYTHON) -m pytest
DAY1_VENV ?= $(CURDIR)/.venv-day1
ifeq ($(strip $(DAY1_VENV)),)
override DAY1_VENV := $(CURDIR)/.venv-day1
endif
DAY1_PYTHON := $(DAY1_VENV)/bin/python
DAY1_PACKAGE_PATHS := $(DAY0_PACKAGE_PATHS):$(CURDIR)/packages/risk_analytics/src
DAY1_PYTEST := PYTHONPATH="$(CURDIR):$(DAY1_PACKAGE_PATHS)" $(DAY1_PYTHON) -m pytest
DAY0_STATE_ROOT := $(abspath $(CURDIR)/../../../state/day0/integration)
PORTFOLIO_RISK_DATA_ROOT := $(DAY0_STATE_ROOT)/portfolio-risk-data
SERVICEFABRIC_RUNTIME_VENV := $(abspath $(CURDIR)/../../../state/venvs/day0/servicefabric-runtime)
SERVICEFABRIC_HOME := $(DAY0_STATE_ROOT)/servicefabric-home-day0-immutable

.PHONY: env-check
env-check:
> ./scripts/bootstrap/check_environment.sh

.PHONY: repo-check
repo-check:
> ./scripts/bootstrap/check_repository.sh

.PHONY: bootstrap-venv
bootstrap-venv:
> test -x "$(BOOTSTRAP_PYTHON)" || $(PYTHON) -m venv "$(BOOTSTRAP_VENV)"
> $(BOOTSTRAP_PIP) install setuptools==80.9.0 wheel==0.45.1
> $(BOOTSTRAP_PIP) install --no-build-isolation -e vendor/servicefabric/packages/servicefabric_release_readiness

.PHONY: upstream-doctor
upstream-doctor: bootstrap-venv
> $(SERVICEFABRIC_DOCTOR) doctor --repository-root vendor/servicefabric

.PHONY: preflight
preflight: env-check repo-check upstream-doctor
> git diff --check
> @echo "Day 0 preparation preflight: PASS"

.PHONY: clean-bootstrap
clean-bootstrap:
> rm -rf "$(BOOTSTRAP_VENV)"

.PHONY: day0-env
day0-env:
> test -f requirements/day0.lock || { \
>   echo "ERROR: requirements/day0.lock is missing" >&2; \
>   exit 1; \
> }
> DAY0_VENV="$(DAY0_VENV)" ./scripts/day0/bootstrap_environment.sh
> test -x "$(DAY0_PYTHON)" || { \
>   echo "ERROR: Day 0 Python was not created at $(DAY0_PYTHON)" >&2; \
>   exit 1; \
> }
> $(DAY0_PYTHON) -m pip check

.PHONY: test-architecture
test-architecture: day0-env
> $(DAY0_PYTEST) tests/architecture -q

.PHONY: test-domain
test-domain: day0-env
> $(DAY0_PYTEST) tests/contracts tests/domain -q

.PHONY: test-planning
test-planning: day0-env
> $(DAY0_PYTEST) tests/planning -q

.PHONY: test-data
test-data: day0-env
> $(DAY0_PYTEST) tests/data -q

.PHONY: test-capabilities
test-capabilities: day0-env
> $(DAY0_PYTEST) tests/capabilities -q

.PHONY: test-agents
test-agents: day0-env
> $(DAY0_PYTEST) tests/agents -q

.PHONY: test-application
test-application: day0-env
> $(DAY0_PYTEST) tests/application -q

.PHONY: test-integration
test-integration: day0-env
> $(DAY0_PYTEST) tests/integration -q

.PHONY: test-journeys
test-journeys: day0-env
> $(DAY0_PYTEST) tests/journeys -q

.PHONY: verify-wave-0a
verify-wave-0a: test-architecture test-integration
> git diff --check
> @echo "D0-WAVE-0A verification: PASS"

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
> git diff --check
> @echo "D0-WAVE-0B verification: PASS"

.PHONY: verify-wave-0c
verify-wave-0c: verify-wave-0b test-journeys
> git diff --check
> @echo "D0-WAVE-0C verification: PASS"

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
> python3 scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check
> git diff --check
> @echo "Day 0 verification: PASS"

.PHONY: demo-day0-headless
demo-day0-headless: day0-env
> PORTFOLIO_RISK_DATA_ROOT="$(PORTFOLIO_RISK_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(DAY0_PACKAGE_PATHS)" $(DAY0_PYTHON) scripts/day0/run_monitoring_demo.py

.PHONY: servicefabric-smoke
servicefabric-smoke:
> SERVICEFABRIC_RUNTIME_VENV="$(SERVICEFABRIC_RUNTIME_VENV)" \
> SERVICEFABRIC_HOME="$(SERVICEFABRIC_HOME)" \
> PORTFOLIO_RISK_DATA_ROOT="$(PORTFOLIO_RISK_DATA_ROOT)" \
> ./scripts/day0/servicefabric_smoke.sh

.PHONY: day1-prep-context
day1-prep-context:
> $(PYTHON) scripts/day1/show_context.py

.PHONY: verify-day1-prep
verify-day1-prep: day0-env
> $(PYTHON) scripts/day1/check_preparation.py --require-prepared
> $(DAY0_PYTEST) tests/architecture/test_day1_preparation.py -q
> $(MAKE) repo-check
> $(MAKE) test-architecture
> $(PYTHON) scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check
> git diff --check
> @echo "Day 1 preparation verification: PASS"

.PHONY: day1-env
day1-env:
> test -f requirements/day1.lock || { echo "ERROR: requirements/day1.lock is missing" >&2; exit 1; }
> DAY1_VENV="$(DAY1_VENV)" ./scripts/day1/bootstrap_environment.sh
> test -x "$(DAY1_PYTHON)" || { echo "ERROR: Day 1 Python was not created at $(DAY1_PYTHON)" >&2; exit 1; }
> $(DAY1_PYTHON) -m pip check

.PHONY: test-day1-architecture
test-day1-architecture: day1-env
> $(DAY1_PYTEST) tests/architecture/test_day1_preparation.py tests/architecture/test_day1_runtime_boundaries.py -q

.PHONY: test-day1-knowledge
test-day1-knowledge: day1-env
> $(DAY1_PYTEST) tests/planning -q
> if test -d tests/research; then $(DAY1_PYTEST) tests/research -q; else echo "No Day 1 research tests yet"; fi

.PHONY: test-day1-experience
test-day1-experience: day1-env
> $(DAY1_PYTEST) tests/application -q

.PHONY: test-day1-data
test-day1-data: day1-env
> $(DAY1_PYTEST) tests/data -q

.PHONY: test-day1-analytics
test-day1-analytics: day1-env
> $(DAY1_PYTEST) tests/contracts tests/domain -q
> if test -d tests/analytics; then $(DAY1_PYTEST) tests/analytics -q; else echo "No Day 1 analytics tests yet"; fi

.PHONY: test-day1-agents
test-day1-agents: day1-env
> $(DAY1_PYTEST) tests/capabilities tests/agents -q

.PHONY: test-day1-integration
test-day1-integration: day1-env
> $(DAY1_PYTEST) tests/integration -q

.PHONY: test-day1-journeys
test-day1-journeys: day1-env
> $(DAY1_PYTEST) tests/journeys -q

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
> $(DAY1_PYTHON) scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check
> git diff --check
> @echo "D1-WAVE-1A verification: PASS"

.PHONY: verify-wave-1b
verify-wave-1b: verify-wave-1a test-day1-data test-day1-journeys
> git diff --check
> @echo "D1-WAVE-1B verification: PASS"

.PHONY: verify-wave-1c
verify-wave-1c: verify-wave-1b test-day1-analytics test-day1-agents
> git diff --check
> @echo "D1-WAVE-1C verification: PASS"

.PHONY: verify-day1-current
verify-day1-current: day1-env
> $(DAY1_PYTHON) scripts/day1/verify_current.py

.PHONY: verify-day1
verify-day1: verify-wave-1c test-day1-journeys
> $(DAY1_PYTHON) scripts/day1/check_preparation.py
> $(DAY1_PYTHON) scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check
> git diff --check
> @echo "Day 1 verification: PASS"

.PHONY: demo-day1-headless
demo-day1-headless: day1-env
> PORTFOLIO_RISK_DATA_ROOT="$(PORTFOLIO_RISK_DATA_ROOT)" PYTHONPATH="$(CURDIR):$(DAY1_PACKAGE_PATHS)" $(DAY1_PYTHON) scripts/day0/run_monitoring_demo.py

.PHONY: servicefabric-day1-smoke
servicefabric-day1-smoke:
> SERVICEFABRIC_RUNTIME_VENV="$(SERVICEFABRIC_RUNTIME_VENV)" SERVICEFABRIC_HOME="$(SERVICEFABRIC_HOME)" PORTFOLIO_RISK_DATA_ROOT="$(PORTFOLIO_RISK_DATA_ROOT)" ./scripts/day0/servicefabric_smoke.sh
