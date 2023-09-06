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
	sudo docker run --network host -e MESSAGE_ARCHIVE_BUCKET_NAME="llm-message-archive-dev" -e DYNAMODB_HOST="http://localhost:8888" -e DOC_DB_CREDENTIALS_SECRET_NAME="dev/local_mongodb_creds" -e SEARCH_SERVICE_API_URL="http://localhost:8080" -e OPENAI_API_KEY_SECRET_NAME="dev/tai_service/openai/api_key" -e AWS_DEFAULT_REGION="us-east-1" -e LOG_LEVEL="DEBUG" -e DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME="localhost" -e DOC_DB_DATABASE_NAME="class_resources" -e DOC_DB_CLASS_RESOURCE_COLLECTION_NAME="class_resource" -e DOC_DB_PORT="17017" test-container

build-and-run-docker-search-service:
	projen --post false && \
	cdk synth && \
	cd $(DIR) && \
	sudo docker build -t test-container -f $(DOCKER_FILE) . && \
	sudo docker run --network host -e PINECONE_DB_INDEX_NAME="tai-index" -e DOC_DB_CREDENTIALS_SECRET_NAME="dev/local_mongodb_creds" -e DOC_DB_CLASS_RESOURCE_CHUNK_COLLECTION_NAME="class_resource_chunk" -e COLD_STORE_BUCKET_NAME="tai-service-class-resource-cold-store-dev" -e DOCUMENTS_TO_INDEX_QUEUE="tai-service-documents-to-index-queue-dev" -e NLTK_DATA="/tmp/nltk_data" -e MATHPIX_API_SECRET="{"secret_name": "dev/tai_service/mathpix_api_secret"}" -e PINECONE_DB_API_KEY_SECRET_NAME="dev/tai_service/pinecone_db/api_key" -e PINECONE_DB_ENVIRONMENT="us-east-1-aws" -e OPENAI_API_KEY_SECRET_NAME="dev/tai_service/openai/api_key" -e AWS_DEFAULT_REGION="us-east-1" -e LOG_LEVEL="DEBUG" -e DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME="localhost" -e DOC_DB_DATABASE_NAME="class_resources" -e DOC_DB_CLASS_RESOURCE_COLLECTION_NAME="class_resource" test-container

mongodb-start:
	kill $(lsof -t -i:27017); docker run --rm --name mongodb -p 17017:27017 -v /home/ec2-user/tai-service/docker/mongodb:/data/db -e MONGO_INITDB_ROOT_USERNAME=user -e MONGO_INITDB_ROOT_PASSWORD=password mongo

mongodb-stop:
	docker stop mongodb
