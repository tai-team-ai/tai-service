.PHONY: all
all:

deploy-all:
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
	cdk synth && \
	cd $(DIR) && \
	sudo docker build -t test-container -f $(DOCKER_FILE) . && \
	sudo docker run --network host MESSAGE_ARCHIVE_BUCKET_NAME="llm-message-archive-dev" DYNAMODB_HOST="http://localhost:8888" DOC_DB_CREDENTIALS_SECRET_NAME="dev/tai_service/document_DB/read_write_user_password" SEARCH_SERVICE_API_URL="http://localhost:8080" OPENAI_API_KEY_SECRET_NAME="dev/tai_service/openai/api_key" AWS_DEFAULT_REGION="us-east-1" LOG_LEVEL="DEBUG" DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME="tai-service-645860363137.us-east-1.docdb-elastic.amazonaws.com" DOC_DB_DATABASE_NAME="class_resources" DOC_DB_CLASS_RESOURCE_COLLECTION_NAME="class_resource" test-container

build-and-run-docker-search-service:
	cdk synth && \
	cd $(DIR) && \
	sudo docker build -t test-container -f $(DOCKER_FILE) . && \
	sudo docker run --network host PINECONE_DB_INDEX_NAME="tai-index" DOC_DB_CREDENTIALS_SECRET_NAME="dev/tai_service/document_DB/read_write_user_password" DOC_DB_CLASS_RESOURCE_CHUNK_COLLECTION_NAME="class_resource_chunk" COLD_STORE_BUCKET_NAME="tai-service-class-resource-cold-store-dev" DOCUMENTS_TO_INDEX_QUEUE="tai-service-documents-to-index-queue-dev" NLTK_DATA="/tmp/nltk_data" PINECONE_DB_API_KEY_SECRET_NAME="dev/tai_service/pinecone_db/api_key" PINECONE_DB_ENVIRONMENT="us-east-1-aws" OPENAI_API_KEY_SECRET_NAME="dev/tai_service/openai/api_key" AWS_DEFAULT_REGION="us-east-1" LOG_LEVEL="DEBUG" DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME="tai-service-645860363137.us-east-1.docdb-elastic.amazonaws.com" DOC_DB_DATABASE_NAME="class_resources" DOC_DB_CLASS_RESOURCE_COLLECTION_NAME="class_resource" test-container
