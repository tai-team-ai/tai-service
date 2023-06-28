.PHONY: all
all:

deploy: test
	cdk deploy --require-approval never

test:
	python3 -m pytest -vv --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage
