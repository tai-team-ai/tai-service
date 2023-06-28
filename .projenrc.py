from projen.awscdk import AwsCdkPythonApp
from projen.python import VenvOptions, PytestOptions
from projen import Project

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
    ]
)


project.add_git_ignore("/.build/*")

project.synth()
