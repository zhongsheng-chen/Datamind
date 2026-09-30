PYTHON ?= python
NPM ?= npm

CLEAN_TARGETS := build dist datamind/console/dist $(wildcard *.egg-info)

.PHONY: install install-dev install-full install-frontend test \
	test-framework test-frontend test-all lint-frontend build-console build \
	build-docker clean

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[test,release]"

install-full:
	$(PYTHON) -m pip install -e ".[test,release,full]"

install-frontend:
	$(NPM) ci

build-console: install-frontend
	$(NPM) run build:console

test:
	$(PYTHON) -m pytest -ra -m "not framework" tests/unit tests/services tests/cli tests/console

test-framework:
	$(PYTHON) -m pytest -ra -m framework tests/unit

test-frontend: install-frontend
	$(NPM) run test:frontend

test-all: test test-framework test-frontend

lint-frontend: install-frontend
	$(NPM) run lint:console

build: build-console
	$(PYTHON) -m build

build-docker:
	$(PYTHON) -m scripts.build_docker

clean:
	$(RM) -r $(CLEAN_TARGETS)
