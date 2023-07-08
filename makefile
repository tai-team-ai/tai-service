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

build-and-run-docker:
	cd $(DIR) && \
	docker build -t test-container . && \
	docker run -p 9000:8080 -e AWS_LAMBDA_RUNTIME_API=PINECONE_DB_API_KEY_SECRET_NAME -e PINECONE_DB_API_KEY_SECRET_NAME -e PINECONE_DB_ENVIRONMENT -e PINECONE_DB_INDEX_NAME -e DOC_DB_CREDENTIALS_SECRET_NAME -e DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME -e DOC_DB_PORT -e DOC_DB_DATABASE_NAME -e DOC_DB_CLASS_RESOURCE_COLLECTION_NAME -e DOC_DB_CLASS_RESOURCE_CHUNK_COLLECTION_NAME -e OPENAI_API_KEY_SECRET_NAME test-container


test-docker-lambda:
	curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"payload":"hello world!"}'
