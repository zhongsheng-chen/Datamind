PYTHON ?= python
NPM ?= npm

CLEAN_TARGETS := build dist datamind/console/dist $(wildcard *.egg-info)

.PHONY: install install-dev install-full frontend-install console test \
	test-framework frontend-test frontend-lint build docker-build clean

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[test,release]"

install-full:
	$(PYTHON) -m pip install -e ".[test,release,full]"

frontend-install:
	$(NPM) ci

console: frontend-install
	$(NPM) run build:console

test:
	$(PYTHON) -m pytest -ra -m "not framework" tests/unit tests/services tests/cli tests/console

test-framework:
	$(PYTHON) -m pytest -ra -m framework tests/unit

frontend-test: frontend-install
	$(NPM) run test:frontend

frontend-lint: frontend-install
	$(NPM) run lint:console

build: console
	$(PYTHON) -m build

docker-build:
	$(PYTHON) -m scripts.build_docker

clean:
	$(RM) -r $(CLEAN_TARGETS)
