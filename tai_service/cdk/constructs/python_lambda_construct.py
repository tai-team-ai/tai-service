"""Define Lambda properties builder."""
import copy
from os import chmod
from pathlib import Path
import shutil
import tempfile
from typing import Optional, Union
from constructs import Construct
from pydantic import BaseModel, Field, root_validator, validator
from aws_cdk import (
    aws_ec2 as ec2,
    Duration,
    Size as StorageSize,
    aws_lambda as _lambda,
    DockerImage,
    BundlingOptions,
)
from loguru import logger
from.construct_config import BasePydanticSettings
from .construct_helpers import get_vpc, sanitize_name, validate_vpc


TEMP_BUILD_DIR = "/tmp/lambda-build"
MAX_LENGTH_FOR_FUNCTION_NAME = 64

class LambdaURLConfigModel(BaseModel):
    """Define the configuration for the Lambda URL."""

    auth_type: _lambda.FunctionUrlAuthType = Field(
        default=_lambda.FunctionUrlAuthType.AWS_IAM,
        description="The authentication type for the Lambda when using url access.",
    )
    invoke_mode: _lambda.InvokeMode = Field(
        default=_lambda.InvokeMode.BUFFERED,
        description="The invoke mode for the Lambda when using url access.",
    )
    allowed_headers: Optional[list[str]] = Field(
        default=[],
        description="The allowed headers for the Lambda when using url access.",
    )


class PythonLambdaConfigModel(BaseModel):
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
    runtime_environment: BasePydanticSettings = Field(
        ...,
        description="The runtime environment for the Lambda function.",
    )
    requirements_file_path: Path = Field(
        default=None,
        description="The path to the requirements file for the Lambda function.",
    )
    vpc: Optional[Union[ec2.Vpc, str]] = Field(
        default=None,
        description="The VPC to run the Lambda function in.",
    )
    subnet_selection: Optional[ec2.SubnetSelection] = Field(
        default=None,
        description="The subnet selection for the Lambda function to run in.",
    )
    security_groups: Optional[list[ec2.SecurityGroup]] = Field(
        default=[],
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
    function_url: Optional[LambdaURLConfigModel] = Field(
        default=None,
        description="The configuration for the Lambda URL. If provided, the Lambda will be accessible via a URL.",
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

    @validator("function_name")
    def sanitize_function_name(cls, function_name) -> str:
        """Sanitize the function name."""
        return sanitize_name(function_name, MAX_LENGTH_FOR_FUNCTION_NAME)

    @validator("vpc")
    def validate_vpc(cls, vpc) -> Optional[Union[ec2.IVpc, str]]:
        """Validate the VPC."""
        return validate_vpc(vpc)


class PythonLambda(Construct):
    """Define a builder for Python Lambda properties."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: PythonLambdaConfigModel,
        **kwargs,
    ) -> None:
        """Initialize the builder."""
        super().__init__(scope, construct_id, **kwargs)
        self._scope = scope
        config.vpc = get_vpc(scope, config.vpc)
        self._config = config
        self._build_context_folder = Path(f".build-{config.code_path.name}-{config.function_name}")
        self._initialize_build_folder()
        self._function_props_dict = {
            "function_name": config.function_name,
            "description": config.description,
            "handler": f"{config.handler_module_name}.{config.handler_name}",
            "runtime": _lambda.Runtime.PYTHON_3_10,
            "environment": config.runtime_environment.dict(by_alias=True, exclude_none=True, for_environment=True),
            "layers": [],
        }
        self._create_optional_props()
        self._lambda_function: _lambda.Function = _lambda.Function(scope, config.function_name, **self.lambda_props)
        self._create_instantiated_props()

    @property
    def lambda_function(self) -> _lambda.Function:
        """Return the Lambda function."""
        return self._lambda_function

    @property
    def lambda_props(self) -> dict:
        """Return the Lambda properties."""
        function_props = copy.deepcopy(self._function_props_dict)
        build_context_path = str(self._build_context_folder.resolve())
        function_props["code"] = _lambda.Code.from_asset(build_context_path)
        # this validates that the function props are valid
        _lambda.FunctionProps(**function_props)
        return function_props

    @staticmethod
    def get_lambda_function(scope: Construct, construct_id: str, config: PythonLambdaConfigModel) -> _lambda.Function:
        """Return the Lambda function."""
        builder = PythonLambda(scope, construct_id + "python-lambda", config)
        return builder.lambda_function

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
            self._add_vpc_and_subnets()
        if config.security_groups:
            self._function_props_dict["security_groups"] = config.security_groups
        if config.timeout:
            self._function_props_dict["timeout"] = config.timeout
        if config.memory_size:
            self._function_props_dict["memory_size"] = config.memory_size
        if config.ephemeral_storage_size:
            self._function_props_dict["ephemeral_storage_size"] = config.ephemeral_storage_size

    def _create_instantiated_props(self) -> None:
        config = self._config
        if config.function_url:
            self._add_function_url(config.function_url)

    def _add_vpc_and_subnets(self) -> None:
        config = self._config
        self._function_props_dict["vpc"] = config.vpc
        if config.subnet_selection:
            self._function_props_dict["vpc_subnets"] = config.subnet_selection
        if config.subnet_selection.subnet_type == ec2.SubnetType.PUBLIC:
            logger.warning("Lambda is being deployed to a public subnet.")
            self._function_props_dict["allow_public_subnet"] = True

    def _create_layer_with_zip_asset(self) -> None:
        config = self._config
        layer_name = f"{config.function_name}-{config.zip_file_path.stem}"
        layer_zip_file_path = str(config.zip_file_path.resolve())
        layer = _lambda.LayerVersion(
            self._scope,
            layer_name,
            code=_lambda.Code.from_asset(layer_zip_file_path),
        )
        self._add_layer(layer)

    def _copy_files_into_handler_dir(self) -> None:
        with tempfile.TemporaryDirectory(prefix=TEMP_BUILD_DIR) as build_context:
            chmod(build_context, 0o0755)
            for path in self._config.files_to_copy_into_handler_dir:
                destination = Path(build_context) / path.name
                if path.is_file():
                    shutil.copy2(path, destination)
                elif path.is_dir():
                    shutil.copytree(path, destination)
                else:
                    logger.warning(f"Unable to copy {path} into handler directory. Not a file or directory.")
            shutil.copytree(build_context, self._build_context_folder, dirs_exist_ok=True)

    def _create_layer_with_requirements_file(self) -> None:
        config = self._config
        with tempfile.TemporaryDirectory(prefix=TEMP_BUILD_DIR) as build_context:
            chmod(build_context, 0o0755)
            shutil.copy(config.requirements_file_path, build_context)
            runtime: _lambda.Runtime = self._function_props_dict['runtime']
            image_obj: DockerImage = runtime.bundling_image
            install_cmd = f"pip install -r {config.requirements_file_path.name} -t /asset-output/python"
            bundling_options = BundlingOptions(
                image=image_obj,
                command=["bash", "-c", install_cmd],
                user="root",
            )
            code_asset = _lambda.Code.from_asset(build_context, bundling=bundling_options)
            layer = _lambda.LayerVersion(
                self._scope,
                f"{config.function_name}-{config.requirements_file_path.stem}",
                code=code_asset,
                compatible_runtimes=[runtime],
            )
            self._add_layer(layer)

    def _add_layer(self, layer: _lambda.ILayerVersion) -> None:
        layers = self._function_props_dict["layers"]
        layers.append(layer)

    def _add_function_url(self, url_config: LambdaURLConfigModel) -> _lambda.FunctionUrl:
        url = self._lambda_function.add_function_url(
            auth_type=url_config.auth_type,
            cors=_lambda.FunctionUrlCorsOptions(
                allowed_headers=url_config.allowed_headers,
            ),
            invoke_mode=url_config.invoke_mode,
        )
        return url
