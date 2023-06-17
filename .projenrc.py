from projen.awscdk import AwsCdkPythonApp

project = AwsCdkPythonApp(
    author_email="jacobpetterle+aiforu@gmail.com",
    author_name="Jacob Petterle",
    cdk_version="2.1.0",
    module_name="tai_service",
    name="tai-service",
    version="0.1.0",
    deps=[
        "pydantic",
        "loguru",
        "boto3",
        "requests",
        "pymongo",
        "pygit2",
    ],
    dev_deps=[
        "aws-lambda-powertools",
        "aws-lambda-typing",
    ]
)

project.synth()
