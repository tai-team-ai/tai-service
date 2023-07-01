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
)
from ...api.runtime_settings import TaiApiSettings
from .stack_config_models import StackConfigBaseModel
from .stack_helpers  import add_tags
from ..constructs.python_lambda_construct import (
    PythonLambda,
    PythonLambdaConfigModel,
    LambdaURLConfigModel,
)
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
        security_group_allowing_db_connections: ec2.SecurityGroup,
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
        self._python_lambda: PythonLambda = self._create_lambda_function(security_group_allowing_db_connections)
        add_tags(self, config.tags)

    @property
    def lambda_function(self) -> _lambda.Function:
        """Return the lambda function."""
        return self._python_lambda.lambda_function

    def _create_lambda_function(self, security_group_allowing_db_connections: ec2.SecurityGroup) -> PythonLambda:
        config = self._get_lambda_config(security_group_allowing_db_connections)
        name = config.function_name
        python_lambda: PythonLambda = PythonLambda(
            self,
            construct_id=f"{name}-lambda",
            config=config,
        )
        python_lambda.add_read_only_secrets_manager_access([get_secret_arn_from_name(self._settings.secret_name)])
        python_lambda.allow_public_invoke_of_function()
        return python_lambda

    def _get_lambda_config(self, security_group_allowing_db_connections: ec2.SecurityGroup) -> PythonLambdaConfigModel:
        function_name = self._namer("tai-api-service")
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
        subnet_type = ec2.SubnetType.PUBLIC
        assert vpc_interface_exists(ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER, self._vpc),\
            "The VPC must have an interface endpoint for Secrets Manager."
        lambda_config = PythonLambdaConfigModel(
            function_name=function_name,
            description="The lambda for the TAI API service.",
            code_path=API_DIR,
            handler_module_name="index",
            handler_name="handler",
            runtime_environment=self._settings,
            requirements_file_path=API_DIR / "requirements.txt",
            files_to_copy_into_handler_dir=MODULES_TO_COPY_INTO_API_DIR,
            timeout=Duration.minutes(3),
            memory_size=128,
            ephemeral_storage_size=StorageSize.mebibytes(512),
            vpc=self._vpc,
            subnet_selection=ec2.SubnetSelection(subnet_type=subnet_type),
            security_groups=[security_group_secrets, security_group_allowing_db_connections],
            function_url_config=LambdaURLConfigModel(
                allowed_headers=["*"],
                allowed_origins=["*"],
                auth_type=_lambda.FunctionUrlAuthType.NONE,
            ),
        )
        return lambda_config
