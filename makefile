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
	cdk synth && \
	cd $(DIR) && \
	docker build -t test-container . && \
	docker run -p 8000:8000 -e PINECONE_DB_API_KEY_SECRET_NAME="dev/tai_service/pinecone_db/api_key" -e PINECONE_DB_ENVIRONMENT="us-east-1-aws" -e PINECONE_DB_INDEX_NAME="tai-index" -e DOC_DB_CREDENTIALS_SECRET_NAME="dev/tai_service/document_DB/read_write_user_password" -e DOC_DB_USERNAME_SECRET_KEY="username" -e DOC_DB_PASSWORD_SECRET_KEY="password" -e DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME="tai-service-645860363137.us-east-1.docdb-elastic.amazonaws.com" -e DOC_DB_PORT="27017" -e DOC_DB_DATABASE_NAME="class_resources" -e DOC_DB_CLASS_RESOURCE_COLLECTION_NAME="class_resource" -e DOC_DB_CLASS_RESOURCE_CHUNK_COLLECTION_NAME="class_resource_chunk" -e OPENAI_API_KEY_SECRET_NAME="dev/tai_service/openai/api_key" -e AWS_DEFAULT_REGION="us-east-1" test-container

test-docker-lambda:
	curl localhost:8000/
