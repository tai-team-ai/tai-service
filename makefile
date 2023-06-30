.PHONY: all
all:

deploy-all:
	cdk deploy --all --require-approval never

test:
	python3 -m pytest -vv tests --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage

test-deploy-all: test deploy-all

start-docker:
	sudo systemctl start docker
