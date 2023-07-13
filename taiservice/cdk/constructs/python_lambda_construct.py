"""Define Lambda properties builder."""
from abc import ABC, abstractmethod
import builtins
import copy
from enum import Enum
from os import chmod
from pathlib import Path
import shutil
import tempfile
from typing import Optional, Union, Any
from constructs import Construct
from pydantic import BaseModel, Field, root_validator, validator
from aws_cdk import (
    aws_ec2 as ec2,
    Duration,
    Size as StorageSize,
    aws_lambda as _lambda,
    DockerImage,
    BundlingOptions,
    aws_iam as iam,
)
from loguru import logger
from.construct_config import BaseDeploymentSettings
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
    allowed_origins: Optional[list[str]] = Field(
        default=[],
        description="The allowed origins for the Lambda when using url access.",
    )

    @validator("allowed_origins")
    def if_headers_need_cors_then_origins_must_be_set(
        cls, v: list[str], values: dict[str, Any]
    ) -> list[str]:
        """Validate that if headers are set then origins must be set."""
        if values["allowed_headers"] and not v:
            raise ValueError(
                "If allowed_headers is set then allowed_origins must be set."
            )
        return v


class LambdaRuntime(Enum):
    """Define the Lambda runtime options."""

    PYTHON_3_8 = "python:3.8"
    PYTHON_3_9 = "python:3.9"
    PYTHON_3_10 = "python:3.10"


class BaseLambdaConfigModel(BaseModel):
    """Define the configuration for the base Lambda properties builder."""
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
    runtime_environment: BaseDeploymentSettings = Field(
        ...,
        description="The runtime environment for the Lambda function.",
    )
    requirements_file_path: Path = Field(
        default=None,
        description="The path to the requirements file for the Lambda function.",
    )
    vpc: Optional[Any] = Field(
        default=None,
        description="The VPC to run the Lambda function in.",
    )
    subnet_selection: Optional[ec2.SubnetSelection] = Field(
        default=None,
        description="The subnet selection for the Lambda function to run in.",
    )
    security_groups: Optional[list[ec2.SecurityGroup]] = Field(
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
    function_url_config: Optional[LambdaURLConfigModel] = Field(
        default=None,
        description="The configuration for the Lambda URL. If provided, the Lambda will be accessible via a URL.",
    )
    runtime: Optional[LambdaRuntime] = Field(
        default=LambdaRuntime.PYTHON_3_10,
        description="The runtime for the Lambda function.",
    )

    class Config:
        """Define the Pydantic model configuration."""
        arbitrary_types_allowed = True
        validate_assignment = True
        use_enum_values = True

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

    @validator("requirements_file_path")
    def ensure_that_contents_not_blank_space_or_empty(cls, requirements_file_path: Path) -> Optional[Path]:
        """Ensure that the contents of the requirements file are not blank space or empty."""
        if requirements_file_path is not None:
            if requirements_file_path.read_text().strip() == "":
                raise ValueError(f"Requirements file '{requirements_file_path}' is empty. Please provide a valid requirements file " \
                    "with at least package to install.")
        return requirements_file_path


class DockerLambdaConfigModel(BaseLambdaConfigModel):
    """Define the configuration for the Docker Lambda."""

    run_as_webserver: bool = Field(
        default=False,
        description=("Whether or not to run the Lambda as a webserver. "
            "IMPORTANT, if running as a webserver, the handler should point to "
            "a fastAPI factory function."
        )
    )
    custom_docker_commands: list[str] = Field(
        default=[],
        description="A list of custom docker commands to run before final build copy.",
    )


class BaseLambda(Construct):
    """Define the base lambda construct."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: BaseLambdaConfigModel,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._scope = scope
        config.vpc = get_vpc(scope, config.vpc)
        self.security_groups = config.security_groups
        self._function_url = None
        self._config = config
        self._function_props_dict = {
            "function_name": config.function_name,
            "description": config.description,
            "environment": self._config.runtime_environment.dict(by_alias=True, exclude_none=True, for_environment=True),
        }
        self._build_context_folder = Path(f".build-{self._config.code_path.name}-{self._config.function_name}")
        self._initialize_build_folder()
        self._initialize_function_props()
        self._create_optional_props()
        self._lambda_function = self._create_lambda_function()
        self._create_instantiated_props()

    @property
    def lambda_function(self) -> _lambda.Function:
        """Get the Lambda function."""
        return self._lambda_function

    @property
    def function_url(self) -> Optional[str]:
        """Get the function URL."""
        return self._function_url.url

    @property
    def role(self) -> iam.Role:
        """Get the role."""
        return self._lambda_function.role

    @abstractmethod
    def _create_layer_with_zip_asset(self) -> None:
        """Create the layer with the zip asset."""

    @abstractmethod
    def _create_layer_with_requirements_file(self) -> None:
        """Create the layer with the requirements file."""

    @abstractmethod
    def _initialize_function_props(self) -> None:
        """Initialize the function props."""

    @abstractmethod
    def _create_lambda_function(self) -> _lambda.Function:
        """Create the Lambda function."""

    @property
    def lambda_props(self) -> dict:
        """Return the Lambda properties."""
        # this validates that the function props are valid
        _lambda.FunctionProps(**self._function_props_dict)
        return self._function_props_dict

    @staticmethod
    def get_lambda_function(scope: Construct, construct_id: str, config: BaseLambdaConfigModel) -> 'BaseLambda':
        """Return the Lambda function."""
        lambda_func: BaseLambda = PythonLambda(scope, construct_id + "-lambda", config)
        return lambda_func

    def add_read_only_secrets_manager_access(self, arns: list[str]) -> None:
        """Add a read only Secrets Manager policy to the Lambda function."""
        self._lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=arns,
            )
        )

    def allow_public_invoke_of_function(self) -> None:
        """Allow public invoke of the function."""
        self._lambda_function.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["lambda:InvokeFunctionUrl"],
                effect=iam.Effect.ALLOW,
                resources=["*"],
            )
        )

    def add_to_role_policy(self, statement: iam.PolicyStatement) -> None:
        """Add a statement to the role policy."""
        self._lambda_function.add_to_role_policy(statement)

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
        self._function_props_dict["security_groups"] = config.security_groups
        self._function_props_dict["timeout"] = config.timeout
        self._function_props_dict["memory_size"] = config.memory_size
        self._function_props_dict["ephemeral_storage_size"] = config.ephemeral_storage_size

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

    def _add_vpc_and_subnets(self) -> None:
        config = self._config
        self._function_props_dict["vpc"] = config.vpc
        if config.subnet_selection:
            self._function_props_dict["vpc_subnets"] = config.subnet_selection
        if config.subnet_selection.subnet_type == ec2.SubnetType.PUBLIC:
            logger.warning("Lambda is being deployed to a public subnet. If you are trying to connect to the internet, " \
                "you can't from a public subnet with lambda as they do not have public IP addresses. " \
                "You must place the lambda in a private subnet and create a NAT Gateway if you want to connect to the internet.")
            self._function_props_dict["allow_public_subnet"] = True

    def _create_instantiated_props(self) -> None:
        config = self._config
        if config.function_url_config:
            self._function_url = self._add_function_url(config.function_url_config)

    def _add_function_url(self, url_config: LambdaURLConfigModel) -> _lambda.FunctionUrl:
        url = self._lambda_function.add_function_url(
            auth_type=url_config.auth_type,
            cors=_lambda.FunctionUrlCorsOptions(
                allowed_headers=url_config.allowed_headers,
                allowed_origins=url_config.allowed_origins,
            ),
            invoke_mode=url_config.invoke_mode,
        )
        return url


class PythonLambda(BaseLambda):
    """Define the Python Lambda construct."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: BaseLambdaConfigModel,
        **kwargs,
    ) -> None:
        """Initialize the builder."""
        super().__init__(scope, construct_id, config, **kwargs)

    def _initialize_function_props(self) -> None:
        runtime_name = self._config.runtime.value.replace(":", "")
        self._function_props_dict.update({
            "handler": f"{self._config.handler_module_name}.{self._config.handler_name}",
            "runtime": _lambda.Runtime(runtime_name),
            "layers": [],
        })

    def _create_lambda_function(self) -> _lambda.Function:
        build_context_path = str(self._build_context_folder.resolve())
        self._function_props_dict["code"] = _lambda.Code.from_asset(build_context_path)
        lambda_function: _lambda.Function = _lambda.Function(self._scope, self._config.function_name, **self.lambda_props)
        return lambda_function

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

    def _create_layer_with_requirements_file(self) -> None:
        config = self._config
        with tempfile.TemporaryDirectory(prefix=TEMP_BUILD_DIR) as build_context:
            chmod(build_context, 0o0755)
            shutil.copy(config.requirements_file_path, build_context)
            runtime: _lambda.Runtime = self._function_props_dict["runtime"]
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
        layers: list = self._function_props_dict["layers"]
        layers.append(layer)


class DockerLambda(BaseLambda):
    """Define the Docker Lambda construct."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: DockerLambdaConfigModel,
        **kwargs,
    ) -> None:
        """Initialize the builder."""
        if config.run_as_webserver:
            handler_root_dir = "/var/task"
            self._port_env_var_name = "PORT"
        else:
            handler_root_dir = "${LAMBDA_TASK_ROOT}" # this needs to be first to configure the handler root dir
        self._previous_stage_name = "build"
        self._config = config
        self._working_dir_docker_cmd = f"WORKDIR {handler_root_dir}"
        super().__init__(scope, construct_id, config, **kwargs)

    def _initialize_function_props(self) -> None:
        if self._config.run_as_webserver:
            self.dockerfile_content = [
                f"FROM public.ecr.aws/docker/library/{self._config.runtime}-slim-buster AS {self._previous_stage_name}",
                "COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.7.0 /lambda-adapter /opt/extensions/lambda-adapter",
            ]
        else:
            self.dockerfile_content = [f"FROM public.ecr.aws/lambda/{self._config.runtime} AS {self._previous_stage_name}"]

    def _add_custom_docker_commands(self) -> None:
        stage_name = "add-custom-docker-commands"
        self.dockerfile_content.append(f"FROM {self._previous_stage_name} AS {stage_name}")
        self.dockerfile_content.extend(self._config.custom_docker_commands)
        self._previous_stage_name = stage_name

    def _create_docker_file(self) -> str:
        if self._config.custom_docker_commands:
            self._add_custom_docker_commands()
        self._copy_build_context_to_container()
        self._add_handler_cmd()
        docker_file_path = Path(self._build_context_folder) / "Dockerfile"
        with open(docker_file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.dockerfile_content))
        return docker_file_path

    def _copy_build_context_to_container(self) -> None:
        stage_name = "add-build-context"
        contents = [
            f"FROM {self._previous_stage_name} AS {stage_name}",
            f"ENV {self._port_env_var_name}=8000", 
            self._working_dir_docker_cmd,
            "COPY . .",
        ]
        self.dockerfile_content.extend(contents)
        self._previous_stage_name = stage_name

    def _add_handler_cmd(self) -> None:
        handler_separator = ":" if self._config.run_as_webserver else "."
        fully_qualified_handler_name = f"{self._config.handler_module_name}{handler_separator}{self._config.handler_name}"
        if self._config.run_as_webserver:
            command = f"CMD exec uvicorn --port ${self._port_env_var_name} --factory {fully_qualified_handler_name}"
        else:
            command = f"CMD [ \"{fully_qualified_handler_name}\" ]"
        self.dockerfile_content.append(command)

    def _create_layer_with_zip_asset(self) -> None:
        config = self._config
        layer_zip_file_path = str(config.zip_file_path.resolve())
        self.dockerfile_content.append(f"COPY --from=0 {layer_zip_file_path} /")

    def _create_layer_with_requirements_file(self) -> None:
        config = self._config
        shutil.copy(config.requirements_file_path, self._build_context_folder)
        install_cmd = f"pip install --no-cache-dir pip && pip install -r {config.requirements_file_path.name}"
        contents = [
            self._working_dir_docker_cmd,
            f"COPY {config.requirements_file_path.name} .",
            f"RUN {install_cmd} && find . -name '*.pyc' -delete",
        ]
        self.dockerfile_content.extend(contents)
        if config.run_as_webserver:
            self.dockerfile_content.append("RUN pip install uvicorn")

    def _create_lambda_function(self) -> _lambda.DockerImageFunction:
        build_context_path = str(self._build_context_folder.resolve())
        self._create_docker_file()
        self._function_props_dict.update({
            "code": _lambda.DockerImageCode.from_image_asset(build_context_path),
        })
        lambda_function: _lambda.DockerImageFunction = _lambda.DockerImageFunction(
            self._scope,
            self._config.function_name,
            **self._function_props_dict,
        )
        return lambda_function
