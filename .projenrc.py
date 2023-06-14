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
    ]
)

project.synth()