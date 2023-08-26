.PHONY: all
all:

synth:
	projen --post false

deploy-all:
	projen --post false && \
	cdk deploy --all --require-approval never

unit-test:
	python3 -m pytest -vv tests/unit --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage

functional-test:
	python3 -m pytest -vv tests/functional --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage

full-test: unit-test functional-test

docker-start:
	sudo systemctl start docker

ecr-docker-login:
	aws ecr get-login-password --region=$(REGION) | $(SUDO) docker login --username AWS --password-stdin 763104351884.dkr.ecr.$(REGION).amazonaws.com
	aws ecr get-login-password --region=$(REGION) | $(SUDO) docker login --username AWS --password-stdin $(ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com

test-docker-lambda:
	curl localhost:$(PORT)

docker-clean-all-force:
	docker system prune --all --force

build-and-run-docker-api:
	projen --post false && \
	cdk synth && \
	cd $(DIR) && \
	sudo docker build -t test-container -f $(DOCKER_FILE) . && \
	sudo docker run --network host -e MESSAGE_ARCHIVE_BUCKET_NAME="llm-message-archive-dev" -e DYNAMODB_HOST="http://localhost:8888" -e DOC_DB_CREDENTIALS_SECRET_NAME="dev/tai_service/document_DB/read_ONLY_user_password" -e SEARCH_SERVICE_API_URL="http://localhost:8080" -e OPENAI_API_KEY_SECRET_NAME="dev/tai_service/openai/api_key" -e AWS_DEFAULT_REGION="us-east-1" -e LOG_LEVEL="DEBUG" -e DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME="tai-service-645860363137.us-east-1.docdb-elastic.amazonaws.com" -e DOC_DB_DATABASE_NAME="class_resources" -e DOC_DB_CLASS_RESOURCE_COLLECTION_NAME="class_resource" test-container

build-and-run-docker-search-service:
	projen --post false && \
	cdk synth && \
	cd $(DIR) && \
	sudo docker build -t test-container -f $(DOCKER_FILE) . && \
	sudo docker run --network host -e PINECONE_DB_INDEX_NAME="tai-index" -e DOC_DB_CREDENTIALS_SECRET_NAME="dev/tai_service/document_DB/read_write_user_password" -e DOC_DB_CLASS_RESOURCE_CHUNK_COLLECTION_NAME="class_resource_chunk" -e COLD_STORE_BUCKET_NAME="tai-service-class-resource-cold-store-dev" -e DOCUMENTS_TO_INDEX_QUEUE="tai-service-documents-to-index-queue-dev" -e NLTK_DATA="/tmp/nltk_data" -e PINECONE_DB_API_KEY_SECRET_NAME="dev/tai_service/pinecone_db/api_key" -e PINECONE_DB_ENVIRONMENT="us-east-1-aws" -e OPENAI_API_KEY_SECRET_NAME="dev/tai_service/openai/api_key" -e AWS_DEFAULT_REGION="us-east-1" -e LOG_LEVEL="DEBUG" -e DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME="tai-service-645860363137.us-east-1.docdb-elastic.amazonaws.com" -e DOC_DB_DATABASE_NAME="class_resources" -e DOC_DB_CLASS_RESOURCE_COLLECTION_NAME="class_resource" test-container
