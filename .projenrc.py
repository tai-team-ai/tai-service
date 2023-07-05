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
        "pydantic",
        "loguru",
        "boto3",
        "requests",
        "pymongo",
        "pygit2",
        "pinecone-client[grpc]",
        "pydantic[dotenv]",
        "fastapi<=0.98.0",
        "mangum",
    ],
    dev_deps=[
        "aws-lambda-powertools",
        "aws-lambda-typing",
        "boto3-stubs[secretsmanager]",
        "boto3-stubs[essential]",
        "pytest",
        "pytest-cov",
        "uvicorn",
        "pinecone-client[grpc]",
        "langchain",
        "ipykernel",
        "pymongo",
        "filetype",
        "boto3-stubs[essential]",
        "beautifulsoup4",
        "openai",
        "tiktoken",
        "aws-lambda-powertools",
        "pinecone-text",
        # "pinecone-text[splade]", # this installs cuda too, which we don't want
        "torch -f https://download.pytorch.org/whl/cpu",
        "transformers",
    ],
)

env_file: TextFile = TextFile(
    project,
    "./.env",
    lines=[
        'PINECONE_DB_API_KEY_SECRET_NAME="dev/tai_service/pinecone_db/api_key"',
        'OPENAI_API_KEY_SECRET_NAME="dev/tai_service/openai/api_key"',
        'PINECONE_DB_ENVIRONMENT="us-east-1-aws"',
        'DOC_DB_READ_ONLY_USER_PASSWORD_SECRET_NAME="dev/tai_service/document_DB/read_ONLY_user_password"',
        'DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME="dev/tai_service/document_DB/read_write_user_password"',
        'DOC_DB_ADMIN_USER_PASSWORD_SECRET_NAME="dev/tai_service/document_DB/admin_password"',
        'AWS_DEPLOYMENT_ACCOUNT_ID="645860363137"',
    ]
)
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
    targets=["test"],
    recipe=[
        "python3 -m pytest -vv tests --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage",
    ]
)
make_file.add_rule(
    targets=["test-deploy-all"],
    prerequisites=["test", "deploy-all"],
)
make_file.add_rule(
    targets=["start-docker"],
    recipe=[
        "sudo systemctl start docker",
    ],
)

vscode = VsCode(project)
vscode_launch_config: VsCodeLaunchConfig = VsCodeLaunchConfig(vscode)
vscode_launch_config.add_configuration(
    name="FastAPI",
    type="python",
    request="launch",
    program="${workspaceFolder}/.venv/bin/uvicorn",
    args=[
        "taiservice.api.main:create_app",
        "--reload",
        "--factory"
    ],
    env={
        "PINECONE_DB_API_KEY_SECRET_NAME": "dev/tai_service/pinecone_db/api_key",
        "PINECONE_DB_ENVIRONMENT": "us-east-1-aws",
        "PINCEONE_DB_INDEX_NAME": "tai_service",
        "DOC_DB_CREDENTIALS_SECRET_NAME": "dev/tai_service/document_DB/read_write_user_password",
        "DOC_DB_USERNAME_SECRET_KEY": "username",
        "DOC_DB_PASSWORD_SECRET_KEY": "password",
        "DOC_DB_FULLY_QUALIFIED_DOMAIN_NAME": "tai-service-645860363137.us-east-1.docdb-elastic.amazonaws.com",
        "DOC_DB_PORT": "27017",
        "DOC_DB_DATABASE_NAME": "tai_service",
        "DOC_DB_COLLECTION_NAME": "tai_service",
        "OPENAI_API_KEY_SECRET_NAME": "dev/tai_service/openai/api_key",
    },
)
vscode_settings: VsCodeSettings = VsCodeSettings(vscode)
vscode_settings.add_setting("python.formatting.provider", "none")
vscode_settings.add_setting("python.testing.pytestEnabled", True)
vscode_settings.add_setting("python.testing.pytestArgs", ["tests"])
vscode_settings.add_setting("editor.formatOnSave", True)

project.add_git_ignore(".build*")

project.synth()
