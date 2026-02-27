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
	python -m unittest discover

# ============================================================================ #
# BUILD 
# ============================================================================ #

## build-dist: : Build the distribution archives
.PHONY: build-dist
build-dist:
	pip install wheel twine
	python setup.py sdist bdist_wheel

## build-upload: TAG: Upload the distribution archives
.PHONY: build-upload
build-upload: TAG
	python -m twine upload dist/stackedup-${TAG}*

# ============================================================================ #
# QUALITY CONTROL
# ============================================================================ #

## install: : Install the requirements
.PHONY: install
install:
	pip install setuptools black
	python setup.py develop

## fmt-check: : Run all the format checks
.PHONY: fmt-check
fmt-check: fmt-check-python
	 @echo "Passed format checks"

## fmt-python: : Apply code formatting rules
.PHONY: fmt-python
fmt-python:
	black --line-length=80 .

## fmt-check-python: : Check code for incorrect formatting
.PHONY: fmt-check-python
fmt-check-python:
	black --line-length=80 --diff --check .

## fmt-md: : Format the md files
.PHONY: fmt-md
fmt-md:
	prettier README.md -w
