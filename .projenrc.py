import copy
from typing import Literal, Union
from projen.awscdk import AwsCdkPythonApp
from projen.python import VenvOptions
from projen.vscode import (
    VsCode,
    VsCodeLaunchConfig,
    VsCodeSettings,
)
from projen import (
    Project,
    Makefile,
    TextFile,
)


def convert_dict_env_vars_to_env_vars(env_vars: dict, output: Literal["string", "list"] = "string") -> Union[str, list]:
    """Convert a dictionary of environment variables to a string or list of strings."""
    if output == "string":
        return " ".join([f"{key}=\"{value}\"" for key, value in env_vars.items()])
    elif output == "list":
        return [f"{key}=\"{value}\"" for key, value in env_vars.items()]


VENV_DIR = ".venv"
project:Project = AwsCdkPythonApp(
    author_email="jacobpetterle+aiforu@gmail.com",
    author_name="Jacob Petterle",
    cdk_version="2.85.0",
    module_name="taiservice",
    name="tai-service",
    version="0.1.0",
    venv_options=VenvOptions(envdir=VENV_DIR),
    deps=[
        "tai-aws-account-bootstrap",
        "pydantic<=1.10.11",
        "loguru",
        "boto3",
        "requests",
        "pymongo",
        "pygit2",
        "fastapi<=0.98.0",
        "pydantic[dotenv]<=1.10.11",
        "aws-lambda-powertools",
        "aws-lambda-typing",
        "boto3-stubs[secretsmanager]",
        "boto3-stubs[essential]",
        "pytest",
        "pytest-cov",
        "uvicorn",
        "pinecone-client[grpc]",
        "langchain==0.0.229",
        "ipykernel",
        "pymongo",
        "filetype",
        "boto3-stubs[essential]",
        "beautifulsoup4",
        "openai",
        "tiktoken",
        "aws-lambda-powertools",
        "pinecone-text[splade]",
        # "torch -f https://download.pytorch.org/whl/cpu",
        # "transformers",
        "pymupdf",
        "pdf2image",
        "PyPDF2",
        "unstructured",
        "selenium",
        "pynamodb",
        "tiktoken",
    ],
)


SEARCH_SERVICE_API_URL = {"SEARCH_SERVICE_API_URL": "http://tai-s-taise-125N3549KKY44-808887776.us-east-1.elb.amazonaws.com"}
PINECONE_DB_ENVIRONMENT = {"PINECONE_DB_ENVIRONMENT": "us-east-1-aws"}
PINECONE_DB_API_KEY_SECRET_NAME = {"PINECONE_DB_API_KEY_SECRET_NAME": "dev/tai_service/pinecone_db/api_key"}
OPENAI_API_KEY_SECRET_NAME = {"OPENAI_API_KEY_SECRET_NAME": "dev/tai_service/openai/api_key"}
DOC_DB_READ_ONLY_USER_PASSWORD_SECRET_NAME = "dev/tai_service/document_DB/read_ONLY_user_password"
DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME = "dev/tai_service/document_DB/read_write_user_password"
AWS_DEFAULT_REGION = {"AWS_DEFAULT_REGION": "us-east-1"}

ENV_FILE_VARS = {
    "DOC_DB_READ_ONLY_USER_PASSWORD_SECRET_NAME": DOC_DB_READ_ONLY_USER_PASSWORD_SECRET_NAME,
    "DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME": DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME,
    "DOC_DB_ADMIN_USER_PASSWORD_SECRET_NAME": "dev/tai_service/document_DB/admin_password",
    "AWS_DEPLOYMENT_ACCOUNT_ID": "645860363137",
    "DEPLOYMENT_TYPE": "dev",
    "VPC_ID": "vpc-0fdc1f2e77f6dba96",
} | SEARCH_SERVICE_API_URL | PINECONE_DB_ENVIRONMENT | PINECONE_DB_API_KEY_SECRET_NAME | OPENAI_API_KEY_SECRET_NAME

API_RUNTIME_ENV_VARS = {
    "MESSAGE_ARCHIVE_BUCKET_NAME": "llm-message-archive-dev",
    "DYNAMODB_HOST": "http://localhost:8888",
} | SEARCH_SERVICE_API_URL | OPENAI_API_KEY_SECRET_NAME | AWS_DEFAULT_REGION

SEARCH_SERVICE_RUNTIME_ENV_VARS = {
    "PINECONE_DB_INDEX_NAME": "tai-index",
    "DOC_DB_CREDENTIALS_SECRET_NAME": DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME,
    "DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME": "tai-service-645860363137.us-east-1.docdb-elastic.amazonaws.com",
    "DOC_DB_DATABASE_NAME": "class_resources",
    "DOC_DB_CLASS_RESOURCE_COLLECTION_NAME": "class_resource",
    "DOC_DB_CLASS_RESOURCE_CHUNK_COLLECTION_NAME": "class_resource_chunk",
    "COLD_STORE_BUCKET_NAME": "tai-service-class-resource-cold-store-dev",
    "DOCUMENTS_TO_INDEX_QUEUE": "tai-service-documents-to-index-queue-dev",
    "NLTK_DATA": "/tmp/nltk_data",
} | PINECONE_DB_API_KEY_SECRET_NAME | PINECONE_DB_ENVIRONMENT | OPENAI_API_KEY_SECRET_NAME | AWS_DEFAULT_REGION

env_file: TextFile = TextFile(
    project,
    "./.env",
    lines=convert_dict_env_vars_to_env_vars(ENV_FILE_VARS, output="list"),
)


vscode = VsCode(project)
vscode_settings: VsCodeSettings = VsCodeSettings(vscode)
vscode_settings.add_setting("python.formatting.provider", "none")
vscode_settings.add_setting("python.testing.pytestEnabled", True)
vscode_settings.add_setting("python.testing.pytestArgs", ["tests"])
vscode_settings.add_setting("editor.formatOnSave", True)
vscode_launch_config: VsCodeLaunchConfig = VsCodeLaunchConfig(vscode)

vscode_launch_config.add_configuration(
    name="TAI API",
    type="python",
    request="launch",
    program="${workspaceFolder}/.venv/bin/uvicorn",
    args=[
        "taiservice.api.main:create_app",
        "--reload",
        "--factory",
        "--port",
        "8000",
    ],
    env=API_RUNTIME_ENV_VARS,
)
vscode_launch_config.add_configuration(
    name="TAI Search Service",
    type="python",
    request="launch",
    program="${workspaceFolder}/.venv/bin/uvicorn",
    args=[
        "taiservice.searchservice.main:create_app",
        "--reload",
        "--factory",
        "--port",
        "8080",
    ],
    env=SEARCH_SERVICE_RUNTIME_ENV_VARS,
)


UNITTEST_TARGET_NAME = "unit-test"
FUNCTIONAL_TEST_TARGET_NAME = "functional-test"
FULL_TEST_TARGET_NAME = "full-test"
BASE_DOCKER_RUN_RECIPE = [
    "cdk synth && \\",
    "cd $(DIR) && \\",
    "sudo docker build -t test-container -f $(DOCKER_FILE) . && \\",
]

make_file: Makefile = Makefile(
    project,
    "./makefile",
)
make_file.add_rule(
    targets=["deploy-all"],
    recipe=[
        "cdk deploy --all --require-approval never",
    ],
)
make_file.add_rule(
    targets=[UNITTEST_TARGET_NAME],
    recipe=[
        "python3 -m pytest -vv tests/unit --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage",
    ]
)
make_file.add_rule(
    targets=[FUNCTIONAL_TEST_TARGET_NAME],
    recipe=[
        "python3 -m pytest -vv tests/functional --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage",
    ]
)
make_file.add_rule(
    targets=[FULL_TEST_TARGET_NAME],
    prerequisites=[UNITTEST_TARGET_NAME, FUNCTIONAL_TEST_TARGET_NAME],
)
make_file.add_rule(
    targets=["docker-start"],
    recipe=[
        "sudo systemctl start docker",
    ],
)
make_file.add_rule(
    targets=["ecr-docker-login"],
    recipe=[
        "aws ecr get-login-password --region=$(REGION) | $(SUDO) docker login --username AWS --password-stdin 763104351884.dkr.ecr.$(REGION).amazonaws.com",
        "aws ecr get-login-password --region=$(REGION) | $(SUDO) docker login --username AWS --password-stdin $(ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com",
    ],
)
make_file.add_rule(
    targets=["test-docker-lambda"],
    recipe=[
        "curl localhost:$(PORT)",
    ],
)
make_file.add_rule(
    targets=["docker-clean-all-force"],
    recipe=[
        "docker system prune --all --force",
    ],
)
make_file.add_rule(
    targets=["build-and-run-docker-api"],
    recipe=[
        *BASE_DOCKER_RUN_RECIPE,
        f"sudo docker run --network host {convert_dict_env_vars_to_env_vars(API_RUNTIME_ENV_VARS)} test-container",
    ],
)
make_file.add_rule(
    targets=["build-and-run-docker-search-service"],
    recipe=[
        *BASE_DOCKER_RUN_RECIPE,
        f"sudo docker run --network host {convert_dict_env_vars_to_env_vars(SEARCH_SERVICE_RUNTIME_ENV_VARS)} test-container",
    ],
)


project.add_git_ignore(".build*")
project.add_git_ignore("docker**")

docker_ignore_file: TextFile = TextFile(
    project,
    "./.dockerignore",
    lines=[
        ".git",
        ".gitignore",
        "**/.venv",
        "**/venv",
        "**/tests",
        "**/test-reports",
        "**/.build*/",
    ],
)


project.synth()
