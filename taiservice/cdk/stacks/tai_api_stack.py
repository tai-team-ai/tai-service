"""Define the stack for the TAI API service."""
from typing import Union
from pathlib import Path
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_ec2 as ec2,
    Duration,
    Size as StorageSize,
    CfnOutput,
)
from ...api.runtime_settings import TaiApiSettings
from .stack_config_models import StackConfigBaseModel
from .stack_helpers  import add_tags
from ..constructs.lambda_construct import (
    DockerLambda,
    DockerLambdaConfigModel,
    BaseLambdaConfigModel,
    LambdaURLConfigModel,
    LambdaRuntime,
)
from ..constructs.bucket_construct import VersionedBucket
from ..constructs.construct_config import Permissions
from ..constructs.construct_helpers import (
    get_secret_arn_from_name,
    create_restricted_security_group,
    get_vpc,
    vpc_interface_exists,
)


CDK_DIR = Path(__file__).parent.parent
API_DIR = CDK_DIR.parent / "api"
CONSTRUCT_DIR = CDK_DIR / "constructs"
DOC_DB_CUSTOM_RESOURCE_DIR = CONSTRUCT_DIR / "customresources" / "document_db"
MODULES_TO_COPY_INTO_API_DIR = [
    CONSTRUCT_DIR / "construct_config.py",
    DOC_DB_CUSTOM_RESOURCE_DIR / "settings.py",
]

class TaiApiStack(Stack):
    """Define the stack for the TAI API service."""

    def __init__(
        self,
        scope: Construct,
        config: StackConfigBaseModel,
        api_settings: TaiApiSettings,
        vpc: Union[ec2.IVpc, ec2.Vpc, str],
    ) -> None:
        """Initialize the stack for the TAI API service."""
        super().__init__(
            scope=scope,
            id=config.stack_id,
            stack_name=config.stack_name,
            description=config.description,
            env=config.deployment_settings.aws_environment,
            tags=config.tags,
            termination_protection=config.termination_protection,
        )
        self._namer = lambda name: f"{config.stack_name}-{name}"
        self._settings = api_settings
        self._vpc = get_vpc(self, vpc)
        self._removal_policy = config.removal_policy
        self._stack_suffix = config.stack_suffix
        name_with_suffix = (api_settings.message_archive_bucket_name + self._stack_suffix)[:63]
        api_settings.message_archive_bucket_name = name_with_suffix
        self._python_lambda: DockerLambda = self._create_lambda_function()
        lambda_role = self._python_lambda.role
        self._message_archive_bucket: VersionedBucket = VersionedBucket.create_bucket(
            scope=self,
            bucket_name=api_settings.message_archive_bucket_name,
            public_read_access=False,
            role=lambda_role,
            permissions=Permissions.READ_WRITE,
            removal_policy=self._removal_policy,
        )
        add_tags(self, config.tags)
        CfnOutput(
            self,
            id="FunctionURL",
            value=self._python_lambda.function_url,
            description="The URL of the lambda function.",
        )

    @property
    def lambda_function(self) -> _lambda.Function:
        """Return the lambda function."""
        return self._python_lambda.lambda_function

    def _create_lambda_function(self) -> DockerLambda:
        config = self._get_lambda_config()
        name = config.function_name
        python_lambda: DockerLambda = DockerLambda(
            self,
            construct_id=f"{name}-lambda",
            config=config,
        )
        secrets = [
            self._settings.openAI_api_key_secret_name,
        ]
        python_lambda.add_read_only_secrets_manager_access(arns=[get_secret_arn_from_name(secret) for secret in secrets])
        python_lambda.allow_public_invoke_of_function()
        return python_lambda

    def _get_lambda_config(self) -> BaseLambdaConfigModel:
        function_name = self._namer("handler")
        security_group_secrets = create_restricted_security_group(
            scope=self,
            name=function_name + "-sg",
            description="The security group for the DocumentDB lambda.",
            vpc=self._vpc,
        )
        security_group_secrets.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow outbound HTTPS traffic to Secrets Manager.",
        )
        subnet_type = ec2.SubnetType.PRIVATE_WITH_EGRESS
        assert vpc_interface_exists(ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER, self._vpc),\
            "The VPC must have an interface endpoint for Secrets Manager."
        lambda_config = DockerLambdaConfigModel(
            function_name=function_name,
            description="The lambda for the TAI API service.",
            code_path=API_DIR,
            runtime=LambdaRuntime.PYTHON_3_10,
            handler_module_name="main",
            handler_name="create_app",
            runtime_environment=self._settings,
            requirements_file_path=API_DIR / "requirements.txt",
            files_to_copy_into_handler_dir=MODULES_TO_COPY_INTO_API_DIR,
            timeout=Duration.minutes(15),
            memory_size=10000,
            ephemeral_storage_size=StorageSize.gibibytes(3),
            vpc=self._vpc,
            subnet_selection=ec2.SubnetSelection(subnet_type=subnet_type),
            security_groups=[security_group_secrets],
            function_url_config=LambdaURLConfigModel(
                allowed_headers=["*"],
                allowed_origins=["*"],
                auth_type=_lambda.FunctionUrlAuthType.NONE,
            ),
            run_as_webserver=True,
        )
        return lambda_config
