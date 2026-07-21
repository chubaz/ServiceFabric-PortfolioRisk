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

.PHONY: env-check
env-check:
> ./scripts/bootstrap/check_environment.sh

.PHONY: repo-check
repo-check:
> ./scripts/bootstrap/check_repository.sh

.PHONY: bootstrap-venv
bootstrap-venv:
> test -x "$(BOOTSTRAP_PYTHON)" || $(PYTHON) -m venv "$(BOOTSTRAP_VENV)"
> $(BOOTSTRAP_PIP) install -e vendor/servicefabric/packages/servicefabric_release_readiness

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
verify-day0: preflight verify-wave-0a verify-wave-0b verify-wave-0c
> @echo "Day 0 verification: PASS"
