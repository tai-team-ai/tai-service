"""Define Lambda properties builder."""
from pathlib import Path
import shutil
from typing import Optional, Union
from constructs import Construct
from pydantic import BaseModel, Field, root_validator, validator, BaseSettings
from aws_cdk import (
    aws_ec2 as ec2,
    Duration,
    Size as StorageSize,
    aws_lambda as _lambda,
)

from tai_service.cdk.constructs.construct_helpers import get_vpc, sanitize_name

LAMBDA_RUNTIME_ENVIRONMENT_TYPES = Union[BaseSettings]

TEMP_BUILD_DIR = Path("/tmp/build")
MAX_LENGTH_FOR_FUNCTION_NAME = 64

class PythonLambdaPropsBuilderConfigModel(BaseModel):
    """Define the configuration for the Python Lambda properties builder."""

    function_name: str = Field(
        ...,
        description="The name of the Lambda function.",
    )
    description: str = Field(
        ...,
        description="The description of the Lambda function. This should describe the purpose of the Lambda function.",
    )
    code_path: Path = Field(
        ...,
        description="The path to the Lambda code where the handler is located.",
    )
    handler_module_name: str = Field(
        ...,
        description="The name of the handler module. This is the name of the file where the handler function is located.",
    )
    handler_name: str = Field(
        ...,
        description="The name of the handler function. This is the entry point to the Lambda code.",
    )
    runtime_environment: LAMBDA_RUNTIME_ENVIRONMENT_TYPES = Field(
        ...,
        description="The runtime environment for the Lambda function.",
    )
    requirements_file_path: Path = Field(
        default=None,
        description="The path to the requirements file for the Lambda function.",
    )
    vpc: Optional[ec2.IVpc] = Field(
        default=None,
        description="The VPC to run the Lambda function in.",
    )
    subnet_selection: Optional[ec2.SubnetSelection] = Field(
        default=None,
        description="The subnet selection for the Lambda function to run in.",
    )
    security_groups: Optional[list[ec2.ISecurityGroup]] = Field(
        default=None,
        description="The security groups to apply to the Lambda function.",
    )
    files_to_copy_into_handler_dir: Optional[list[Path]] = Field(
        default=None,
        description="A list of files to copy into the Lambda handler directory.",
    )
    zip_file_path: Optional[Path] = Field(
        default=None,
        description="The path to the zip file to use for the first layer of the Lambda function.",
    )
    timeout: Optional[Duration] = Field(
        default=Duration.seconds(30),
        description="The timeout for the Lambda function.",
    )
    memory_size: Optional[int] = Field(
        default=128,
        description="The memory size for the Lambda function.",
    )
    ephemeral_storage_size: Optional[StorageSize] = Field(
        default=StorageSize.mebibytes(512),
        description="The ephemeral storage size for the Lambda function.",
    )

    class Config:
        """Define the Pydantic model configuration."""

        arbitrary_types_allowed = True
        validate_assignment = True

    @root_validator
    def validate_vpc_is_provided_if_subnet_selection_is_provided(cls, values) -> dict:
        """Validate that a VPC is provided if a subnet selection is provided."""
        if values["subnet_selection"] is not None and values["vpc"] is None:
            raise ValueError("Must provide a VPC if providing a subnet selection")
        return values

    @validator("vpc", pre=True)
    def validate_vpc(cls, vpc) -> Optional[ec2.IVpc]:
        return get_vpc(vpc)

    @validator("function_name")
    def sanitize_function_name(cls, function_name) -> str:
        """Sanitize the function name."""
        return sanitize_name(function_name, MAX_LENGTH_FOR_FUNCTION_NAME)


class PythonLambdaPropsBuilder:
    """Define a builder for Python Lambda properties."""

    def __init__(self, scope: Construct, config: PythonLambdaPropsBuilderConfigModel) -> None:
        """Initialize the builder."""
        self._scope = scope
        self._config = config
        self._build_context_folder = Path(f".build-{config.code_path.name}-{config.function_name}")
        self._initialize_build_folder()
        self._function_props_dict = {
            "function_name": config.function_name,
            "description": config.description,
            "handler": f"{config.handler_module_name}.{config.handler_name}",
            "runtime": _lambda.Runtime.PYTHON_3_10,
            "environment": config.runtime_environment.dict(by_alias=True),
        }

    def _initialize_build_folder(self) -> None:
        if self._build_context_folder.exists():
            shutil.rmtree(self._build_context_folder)
        shutil.copytree(self._config.code_path, self._build_context_folder)

    def _create_optional_props(self) -> None:
        config = self._config
        if config.zip_file_path:
            self._create_layer_with_zip_asset()
        if config.files_to_copy_into_handler_dir:
            self._copy_files_into_handler_dir()
        if config.requirements_file_path:
            self._create_layer_with_requirements_file()
        if config.vpc:
            self._add_lambda_to_vpc()
        if config.security_groups:
            self._add_security_groups_to_lambda()
        if config.timeout:
            self._function_props_dict["timeout"] = config.timeout
        if config.memory_size:
            self._function_props_dict["memory_size"] = config.memory_size
        if config.ephemeral_storage_size:
            self._function_props_dict["ephemeral_storage_size"] = config.ephemeral_storage_size
