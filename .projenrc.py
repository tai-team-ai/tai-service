from projen.awscdk import AwsCdkPythonApp
from projen.python import VenvOptions
from projen import Project, Makefile, TextFile

project:Project = AwsCdkPythonApp(
    author_email="jacobpetterle+aiforu@gmail.com",
    author_name="Jacob Petterle",
    cdk_version="2.85.0",
    module_name="taiservice",
    name="tai-service",
    version="0.1.0",
    venv_options=VenvOptions(envdir=".venv"),
    deps=[
        "pydantic",
        "loguru",
        "boto3",
        "requests",
        "pymongo",
        "pygit2",
        "pinecone-client[grpc]",
        "pydantic[dotenv]",
        "fastapi",
        "mangum",
    ],
    dev_deps=[
        "aws-lambda-powertools",
        "aws-lambda-typing",
        "boto3-stubs[essential]",
        "pytest",
        "pytest-cov",
    ]
)

make_file: Makefile = Makefile(
    project,
    "./makefile",
)
make_file.add_rule(
    targets=["deploy"],
    prerequisites=["test"],
    recipe=[
        "cdk deploy --require-approval never",
    ],
)
make_file.add_rule(
    targets=["test"],
    recipe=[
        "python3 -m pytest -vv --cov=taiservice --cov-report=term-missing --cov-report=xml:test-reports/coverage.xml --cov-report=html:test-reports/coverage",
    ]
)
env_file: TextFile = TextFile(
    project,
    "./.env",
    committed=False,
    readonly=False,
)

project.add_git_ignore("/.build/*")

project.synth()
