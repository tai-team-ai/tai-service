.PHONY: all
all:

test:
	python3 -m pytest -vv --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage
