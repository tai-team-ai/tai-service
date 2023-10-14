"""Define the stack for the TAI API service."""
from pathlib import Path
from typing import Optional, Any
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_ec2 as ec2,
    Duration,
    Size as StorageSize,
    CfnOutput,
)
from pydantic import BaseSettings, Field
from tai_aws_account_bootstrap.stack_config_models import StackConfigBaseModel
from tai_aws_account_bootstrap.stack_helpers import add_tags
from ...api.runtime_settings import TaiApiSettings
from .stack_config_models import StackConfigBaseModel
from .stack_helpers  import add_tags
from ..constructs.python_lambda_construct import (
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
    get_vpc,
)


CDK_DIR = Path(__file__).parent.parent
API_DIR = CDK_DIR.parent / "api"
CONSTRUCT_DIR = CDK_DIR / "constructs"
DOC_DB_CUSTOM_RESOURCE_DIR = CONSTRUCT_DIR / "customresources" / "document_db"
MODULES_TO_COPY_INTO_API_DIR = [
    CONSTRUCT_DIR / "construct_config.py",
    DOC_DB_CUSTOM_RESOURCE_DIR / "settings.py",
]


class DynamoDBSettings(BaseSettings):
    """Define settings for instantiating the DynamoDB table."""

    table_name: str = Field(
        ...,
        description="The name of the DynamoDB table."
    )
    billing_mode: dynamodb.BillingMode = Field(
        default=dynamodb.BillingMode.PAY_PER_REQUEST,
        description="The billing mode for the DynamoDB table."
    )
    partition_key: dynamodb.Attribute = Field(
        ...,
        description="The partition key attribute definition."
    )
    sort_key: Optional[dynamodb.Attribute] = Field(
        default=None,
        description="The sort key attribute definition."
    )


class TaiApiStack(Stack):
    """Define the stack for the TAI API service."""

    def __init__(
        self,
        scope: Construct,
        config: StackConfigBaseModel,
        api_settings: TaiApiSettings,
        dynamodb_settings: DynamoDBSettings,
        security_group_for_connecting_to_doc_db: ec2.SecurityGroup,
        vpc: Any,
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
        self._api_settings = api_settings
        self._dynamodb_settings = dynamodb_settings
        self._removal_policy = config.removal_policy
        api_settings.cold_store_bucket_name = (api_settings.cold_store_bucket_name + config.stack_suffix)[:63]
        self._cold_store_bucket: VersionedBucket = self._create_bucket(
            name=api_settings.cold_store_bucket_name,
            public_read_access=True,
        )
        self._python_lambda: DockerLambda = self._create_lambda_function(security_group_allowing_db_connections)
        self._cold_store_bucket.grant_write_access(self._python_lambda.role)
        api_settings.frontend_data_transfer_bucket_name = (api_settings.frontend_data_transfer_bucket_name + config.stack_suffix)[:63]
        self._frontend_transfer_bucket: VersionedBucket = self._create_bucket(
            name=api_settings.frontend_data_transfer_bucket_name,
            public_read_access=True,
        )
        self._frontend_transfer_bucket.grant_read_access(self._python_lambda.role)
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

    @property
    def frontend_transfer_bucket(self) -> VersionedBucket:
        """Return the frontend transfer bucket."""
        return self._frontend_transfer_bucket

    def _create_bucket(self, name: str, public_read_access: bool) -> VersionedBucket:
        config = VersionedBucketConfigModel(
            bucket_name=name,
            public_read_access=public_read_access,
            removal_policy=self._removal_policy,
        )
        bucket = VersionedBucket(
            scope=self,
            construct_id=f"{config.bucket_name}-bucket",
            config=config,
        )
        return bucket

    def _create_lambda_function(self, sg_for_connecting_to_doc_db: ec2.SecurityGroup, vpc: ec2.IVpc) -> DockerLambda:
        config = self._get_lambda_config(sg_for_connecting_to_doc_db, vpc)
        name = config.function_name
        python_lambda: DockerLambda = DockerLambda(
            self,
            construct_id=f"{name}-lambda",
            config=config,
        )
        python_lambda.add_read_only_secrets_manager_access(arns=[get_secret_arn_from_name(secret) for secret in self._api_settings.secret_names])
        python_lambda.allow_public_invoke_of_function()
        return python_lambda

    def _get_lambda_config(self, sg_for_connecting_to_doc_db: ec2.SecurityGroup, vpc: ec2.IVpc) -> DockerLambdaConfigModel:
        function_name = self._namer("handler")
        security_group: ec2.SecurityGroup = ec2.SecurityGroup(
            self,
            id=function_name + "-sg",
            security_group_name=function_name,
            description="The security group for the tai api lambda function.",
            vpc=vpc,
            allow_all_outbound=True,
        )
        security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow inbound HTTPS traffic from anywhere",
        )
        lambda_config = DockerLambdaConfigModel(
            function_name=function_name,
            description="The lambda for the TAI API service.",
            code_path=API_DIR,
            runtime=LambdaRuntime.PYTHON_3_10,
            handler_module_name="main",
            handler_name="create_app",
            runtime_environment=self._api_settings,
            requirements_file_path=API_DIR / "requirements.txt",
            files_to_copy_into_handler_dir=MODULES_TO_COPY_INTO_API_DIR,
            timeout=Duration.minutes(15),
            memory_size=512,
            ephemeral_storage_size=StorageSize.gibibytes(3),
            function_url_config=LambdaURLConfigModel(
                allowed_headers=["*"],
                allowed_origins=["*"],
                auth_type=_lambda.FunctionUrlAuthType.NONE,
            ),
            run_as_webserver=True,
            security_groups=[security_group, sg_for_connecting_to_doc_db],
            vpc=vpc,
            subnet_selection=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )
        return lambda_config
