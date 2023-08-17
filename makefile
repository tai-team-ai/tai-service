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

build-and-run-docker-api:
	cdk synth && \
	cd $(DIR) && \
	sudo docker build -t test-container -f $(DOCKER_FILE) . && \
	sudo docker run --network host -e MESSAGE_ARCHIVE_BUCKET_NAME="llm-message-archive-dev" -e OPENAI_API_KEY_SECRET_NAME="dev/tai_service/openai/api_key" -e SEARCH_SERVICE_API_URL="http://tai-s-taise-125N3549KKY44-808887776.us-east-1.elb.amazonaws.com" -e AWS_DEFAULT_REGION="us-east-1" test-container

build-and-run-docker-search-service:
	cdk synth && \
	cd $(DIR) && \
	sudo docker build -t test-container -f $(DOCKER_FILE) . && \
	sudo docker run --network host -e PINECONE_DB_API_KEY_SECRET_NAME="dev/tai_service/pinecone_db/api_key" -e PINECONE_DB_ENVIRONMENT="us-east-1-aws" -e PINECONE_DB_INDEX_NAME="tai-index" -e DOC_DB_CREDENTIALS_SECRET_NAME="dev/tai_service/document_DB/read_write_user_password" -e DOC_DB_USERNAME_SECRET_KEY="username" -e DOC_DB_PASSWORD_SECRET_KEY="password" -e DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME="tai-service-645860363137.us-east-1.docdb-elastic.amazonaws.com" -e DOC_DB_PORT="27017" -e DOC_DB_DATABASE_NAME="class_resources" -e DOC_DB_CLASS_RESOURCE_COLLECTION_NAME="class_resource" -e DOC_DB_CLASS_RESOURCE_CHUNK_COLLECTION_NAME="class_resource_chunk" -e AWS_DEFAULT_REGION="us-east-1" -e COLD_STORE_BUCKET_NAME="tai-service-class-resource-cold-store-dev" -e DOCUMENTS_TO_INDEX_QUEUE="frontend-data-transfer-[branch-name]" -e NLTK_DATA="/tmp/nltk_data" test-container

test-docker-lambda:
	curl localhost:8000/

docker-clean-all-force:
	docker system prune --all --force
