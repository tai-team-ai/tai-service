.PHONY: all
all:

deploy-all:
	cdk deploy --all --require-approval never

unit-test:
	python3 -m pytest -vv tests/unit --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage

functional-test:
	python3 -m pytest -vv tests/functional --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage

full-test: unit-test functional-test

test-deploy-all: full-test deploy-all

start-docker:
	sudo systemctl start docker
