import json
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


def convert_dict_env_vars_to_env_vars(env_vars: dict, output: Literal["docker", "list"] = "docker") -> Union[str, list]:
    """Convert a dictionary of environment variables to a string or list of strings."""
    if output == "docker":
        return " ".join([f'-e {key}="{json.dumps(value)}"' for key, value in env_vars.items()])
    elif output == "list":
        return [f'{key}="{value}"' for key, value in env_vars.items()]
    else:
        raise ValueError(f"Invalid output type: {output}")


PACKAGE_NAME = "taiservice"

VENV_DIR = ".venv"
project: Project = AwsCdkPythonApp(
    author_email="jacobpetterle+aiforu@gmail.com",
    author_name="Jacob Petterle",
    cdk_version="2.85.0",
    module_name=PACKAGE_NAME,
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
        "pymupdf==1.22.5",
        "pdf2image",
        "PyPDF2",
        "unstructured",
        "selenium",
        "pynamodb",
        "tiktoken",
        "psutil",
        "gunicorn",
        "uvicorn[standard]",  # installs high performance ASGI server
        "markdown",
        "youtube-transcript-api",
        "pytube",
        "keybert",
        "webdriver-manager",
        "redis",
    ],
    dev_deps=[
        "black",
        "pyright",
        "uvicorn",
    ],
)


SEARCH_SERVICE_API_URL = {
    "SEARCH_SERVICE_API_URL": "http://localhost:8080"
}  # this gets set during deployment so this is for local dev
PINECONE_DB_ENVIRONMENT = {"PINECONE_DB_ENVIRONMENT": "us-east-1-aws"}
PINECONE_DB_API_KEY_SECRET_NAME = {"PINECONE_DB_API_KEY_SECRET_NAME": "dev/tai_service/pinecone_db/api_key"}
OPENAI_API_KEY_SECRET_NAME = {"OPENAI_API_KEY_SECRET_NAME": "dev/tai_service/openai/api_key"}
DOC_DB_READ_ONLY_USER_PASSWORD_SECRET_NAME = "dev/tai_service/document_DB/read_ONLY_user_password"
DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME = "dev/tai_service/document_DB/read_write_user_password"
DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME = {"DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME": "localhost"}
DOC_DB_DATABASE_NAME = {"DOC_DB_DATABASE_NAME": "class_resources"}
DOC_DB_CLASS_RESOURCE_COLLECTION_NAME = {"DOC_DB_CLASS_RESOURCE_COLLECTION_NAME": "class_resource"}
AWS_DEFAULT_REGION = {"AWS_DEFAULT_REGION": "us-east-1"}
LOG_LEVEL = {"LOG_LEVEL": "DEBUG"}
MONGODB_LOCAL_PORT = {"DOC_DB_PORT": "17017"}

ENV_FILE_VARS = (
    {
        "DOC_DB_READ_ONLY_USER_PASSWORD_SECRET_NAME": DOC_DB_READ_ONLY_USER_PASSWORD_SECRET_NAME,
        "DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME": DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME,
        "DOC_DB_ADMIN_USER_PASSWORD_SECRET_NAME": "dev/tai_service/document_DB/admin_password",
        "AWS_DEPLOYMENT_ACCOUNT_ID": "645860363137",
        "DEPLOYMENT_TYPE": "dev",
        "VPC_ID": "vpc-0fdc1f2e77f6dba96",
    }
    | SEARCH_SERVICE_API_URL
    | PINECONE_DB_ENVIRONMENT
    | PINECONE_DB_API_KEY_SECRET_NAME
    | OPENAI_API_KEY_SECRET_NAME
)

API_RUNTIME_ENV_VARS = (
    {
        "MESSAGE_ARCHIVE_BUCKET_NAME": "llm-message-archive-dev",
        "DYNAMODB_HOST": "http://localhost:8888",
        "DOC_DB_CREDENTIALS_SECRET_NAME": "dev/local_mongodb_creds",
    }
    | SEARCH_SERVICE_API_URL
    | OPENAI_API_KEY_SECRET_NAME
    | AWS_DEFAULT_REGION
    | LOG_LEVEL
    | DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME
    | DOC_DB_DATABASE_NAME
    | DOC_DB_CLASS_RESOURCE_COLLECTION_NAME
    | MONGODB_LOCAL_PORT
)

SEARCH_SERVICE_RUNTIME_ENV_VARS = (
    {
        "PINECONE_DB_INDEX_NAME": "tai-index",
        "DOC_DB_CREDENTIALS_SECRET_NAME": "dev/local_mongodb_creds",
        "DOC_DB_CLASS_RESOURCE_CHUNK_COLLECTION_NAME": "class_resource_chunk",
        "COLD_STORE_BUCKET_NAME": "tai-service-class-resource-cold-store-dev",
        "DOCUMENTS_TO_INDEX_QUEUE": "tai-service-documents-to-index-queue-dev",
        "NLTK_DATA": "/tmp/nltk_data",
        "MATHPIX_API_SECRET": '{"secret_name": "dev/tai_service/mathpix_api_secret"}',
        "CACHE_HOST_NAME": "localhost",
    }
    | PINECONE_DB_API_KEY_SECRET_NAME
    | PINECONE_DB_ENVIRONMENT
    | OPENAI_API_KEY_SECRET_NAME
    | AWS_DEFAULT_REGION
    | LOG_LEVEL
    | DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME
    | DOC_DB_DATABASE_NAME
    | DOC_DB_CLASS_RESOURCE_COLLECTION_NAME
    | MONGODB_LOCAL_PORT
)

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
vscode_settings.add_settings(
    settings={
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": True,
    },
    languages=["python"],
)
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
        "--reload-dir",
        f"{PACKAGE_NAME}/api",
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
        "--reload-dir",
        f"{PACKAGE_NAME}/searchservice",
    ],
    env=SEARCH_SERVICE_RUNTIME_ENV_VARS,
)


UNITTEST_TARGET_NAME = "unit-test"
FUNCTIONAL_TEST_TARGET_NAME = "functional-test"
FULL_TEST_TARGET_NAME = "full-test"
PROJEN_SYNTH_CMD = "projen --post false"
BASE_DOCKER_RUN_RECIPE = [
    f"{PROJEN_SYNTH_CMD} && \\",
    "cdk synth && \\",
    "cd $(DIR) && \\",
    "sudo docker build -t test-container -f $(DOCKER_FILE) . && \\",
]

make_file: Makefile = Makefile(
    project,
    "./makefile",
)
make_file.add_rule(
    targets=["synth"],
    recipe=[
        "projen --post false",
    ],
)
make_file.add_rule(
    targets=["deploy-all"],
    recipe=[
        f"{PROJEN_SYNTH_CMD} && \\",
        "cdk deploy --all --require-approval never",
    ],
)
make_file.add_rule(
    targets=[UNITTEST_TARGET_NAME],
    recipe=[
        "python3 -m pytest -vv tests/unit --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage",
    ],
)
make_file.add_rule(
    targets=[FUNCTIONAL_TEST_TARGET_NAME],
    recipe=[
        "python3 -m pytest -vv tests/functional --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage",
    ],
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
make_file.add_rule(
    targets=["mongodb-start"],
    recipe=[
        "kill $(lsof -t -i:27017); docker run --rm --name mongodb -p 17017:27017 -v /home/ec2-user/tai-service/docker/mongodb:/data/db -e MONGO_INITDB_ROOT_USERNAME=user -e MONGO_INITDB_ROOT_PASSWORD=password mongo",
    ],
)
make_file.add_rule(
    targets=["mongodb-stop"],
    recipe=[
        "docker stop mongodb",
    ],
)
make_file.add_rule(
    targets=["redis-start"],
    recipe=[
        "kill $(lsof -t -i:6379); docker run --rm --name redis-stack-server -p 6379:6379 redis/redis-stack-server:latest",
    ],
)
make_file.add_rule(
    targets=["redis-stop"],
    recipe=[
        "docker stop redis-stack-server",
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
        "**/cdk.out",
        "**/docker",
        "**/tests",
    ],
)


project.synth()
