"""Define the stack for the TAI API service."""
from typing import Union
from pathlib import Path
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_ec2 as ec2,
    Duration,
    Size as StorageSize,
)
from ...api.runtime_settings import TaiApiSettings, MongoDBUser, BaseDocumentDBSettings
from .stack_config_models import StackConfigBaseModel
from ..constructs.python_lambda_construct import (
    PythonLambda,
    PythonLambdaConfigModel,
    LambdaURLConfigModel,
)
from ..constructs.construct_helpers import (
    get_secret_arn_from_name,
    create_restricted_security_group,
    get_vpc,
    create_interface_vpc_endpoint,
)


CDK_DIR = Path(__file__).parent.parent
API_DIR = CDK_DIR.parent / "api"
CONSTRUCT_DIR = CDK_DIR / "constructs"
DOC_DB_CUSTOM_RESOURCE_DIR = CONSTRUCT_DIR / "customresources" / "document_db"


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
        self._settings: Union[MongoDBUser, BaseDocumentDBSettings] = api_settings
        self._vpc = get_vpc(self, vpc)
        self._python_lambda = self._create_lambda_function()

    @property
    def lambda_function(self) -> _lambda.Function:
        """Return the lambda function."""
        return self._python_lambda.lambda_function

    def _create_lambda_function(self) -> PythonLambda:
        config = self._get_lambda_config()
        name = config.function_name
        python_lambda: PythonLambda = PythonLambda(
            self,
            construct_id=f"{name}-lambda",
            config=config,
        )
        python_lambda.add_read_only_secrets_manager_access(get_secret_arn_from_name(self._settings.secret_name))
        python_lambda.allow_public_invoke_of_function()
        return python_lambda

    def _get_lambda_config(self) -> PythonLambdaConfigModel:
        function_name = "tai-service-api"
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
        create_interface_vpc_endpoint(
            scope=self,
            id="SecretsManagerEndpoint",
            vpc=self._vpc,
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            security_groups=[security_group_secrets],
            subnet_type=subnet_type,
        )
        lambda_config = PythonLambdaConfigModel(
            function_name=function_name,
            description="The lambda for the TAI API service.",
            code_path=API_DIR,
            handler_module_name="main",
            handler_name="lambda_handler",
            runtime_environment=self._settings,
            requirements_file_path=API_DIR / "requirements.txt",
            files_to_copy_into_handler_dir=[
                CONSTRUCT_DIR / "construct_config.py",
                DOC_DB_CUSTOM_RESOURCE_DIR / "settings.py",
            ],
            timeout=Duration.minutes(3),
            memory_size=128,
            ephemeral_storage_size=StorageSize.mebibytes(512),
            vpc=self._vpc,
            subnet_selection=ec2.SubnetSelection(subnet_type=subnet_type),
            security_groups=[security_group_secrets],
            function_url_config=LambdaURLConfigModel(allowed_headers=["*"], allowed_origins=["*"]),
        )
        return lambda_config
