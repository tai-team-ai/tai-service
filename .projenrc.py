from projen.awscdk import AwsCdkPythonApp
from projen.python import VenvOptions

project = AwsCdkPythonApp(
    author_email="jacobpetterle+aiforu@gmail.com",
    author_name="Jacob Petterle",
    cdk_version="2.1.0",
    module_name="tai_service",
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
    ],
    dev_deps=[
        "aws-lambda-powertools",
        "aws-lambda-typing",
    ]
)

project.synth()
