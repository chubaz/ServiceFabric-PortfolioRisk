SHELL := /usr/bin/env bash
.RECIPEPREFIX := >

PYTHON ?= python3
BOOTSTRAP_VENV ?= .venv-bootstrap
BOOTSTRAP_PYTHON := $(BOOTSTRAP_VENV)/bin/python
BOOTSTRAP_PIP := $(BOOTSTRAP_PYTHON) -m pip
SERVICEFABRIC_DOCTOR := $(BOOTSTRAP_VENV)/bin/servicefabric

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
