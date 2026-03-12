.DEFAULT_GOAL := help

# Set Makefile variables from .env
# https://lithic.tech/blog/2020-05/makefile-dot-env/
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

# ============================================================================ #
# VARS
# ============================================================================ #

# ============================================================================ #
# HELPERS
# ============================================================================ #

## Command: Variable(s): Description
## -------: -----------: -----------

## help: : Print this help message
.PHONY: help
help:
	@echo 'Usage:'
	@sed -n 's/^##//p' ${MAKEFILE_LIST} | column -t -s ':' |  sed -e 's/^/ /'

guard-%:
	@ if [ -z '${${*}}' ]; then echo 'ERROR: variable $* not set' && exit 1; fi

# ============================================================================ #
# TESTS
# ============================================================================ #

## test: : Run tests
.PHONY: test
test:
	pytest -Wa --color=yes --code-highlight=yes --cache-clear

## coverage: : Run coverage report
.PHONY: coverage
coverage:
	python -m coverage erase
	python -m coverage run -m pytest -q
	python -m coverage report -m

# ============================================================================ #
# BUILD
# ============================================================================ #

## build-dist: : Build the distribution archives
.PHONY: build-dist
build-dist:
	python -m pip install -e ".[publish]"
	python -m build

## build-upload: : Upload the distribution archives
.PHONY: build-upload
build-upload:
	python -m pip install -e ".[publish]"
	python -m twine upload dist/*

## install-dist: : Install the local built distribution archives
.PHONY: install-dist
install-dist:
	python -m pip install dist/stackedup-*.tar.gz

# ============================================================================ #
# QUALITY CONTROL
# ============================================================================ #

## install: : Install the requirements
.PHONY: install
install:
	python -m pip install -e ".[dev]"

## fmt-check: : Run all the format checks
.PHONY: fmt-check
fmt-check: fmt-check-python
	 @echo "Passed format checks"

## fmt-python: : Apply code formatting rules
.PHONY: fmt-python
fmt-python:
	ruff format .

## fmt-check-python: : Check code for incorrect formatting
.PHONY: fmt-check-python
fmt-check-python:
	ruff check .

## fmt-md: : Format the md files
.PHONY: fmt-md
fmt-md:
	prettier README.md -w

# ==================================================================================== #
# Release
# ==================================================================================== #

# Revision when the project started automatically tracking changelog
CHANGELOG_START_REV = "0.0.15"

## changelog/next: Preview the next changelog section for unreleased commits
.PHONY: changelog/next
changelog/next:
	git-cliff --bump -u $(CHANGELOG_START_REV)..

## changelog/generate: Write CHANGELOG.md from all tracked commits
.PHONY: changelog/generate
changelog/generate:
	git-cliff $(CHANGELOG_START_REV).. --output CHANGELOG.md
