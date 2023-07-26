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
    RemovalPolicy,
    aws_iam as iam,
)
from ...api.runtime_settings import TaiApiSettings
from .stack_config_models import StackConfigBaseModel
from .stack_helpers  import add_tags, Permissions
from ..constructs.python_lambda_construct import (
    DockerLambda,
    DockerLambdaConfigModel,
    BaseLambdaConfigModel,
    LambdaURLConfigModel,
    LambdaRuntime,
)
from ..constructs.bucket_construct import VersionedBucket, VersionedBucketConfigModel
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
        self._removal_policy = config.removal_policy
        self._stack_suffix = config.stack_suffix
        self._python_lambda: DockerLambda = self._create_lambda_function(security_group_allowing_db_connections)
        lambda_role = self._python_lambda.role
        self._cold_store_bucket: VersionedBucket = self._create_bucket(
            bucket_name=api_settings.cold_store_bucket_name,
            public_read_access=True,
            role=lambda_role,
            permissions=Permissions.READ_WRITE,
        )
        api_settings.cold_store_bucket_name = self._cold_store_bucket.bucket_name
        self._message_archive_bucket: VersionedBucket = self._create_bucket(
            bucket_name=api_settings.message_archive_bucket_name,
            public_read_access=False,
            role=lambda_role,
            permissions=Permissions.READ_WRITE,
        )
        api_settings.message_archive_bucket_name = self._message_archive_bucket.bucket_name
        self._frontend_transfer_bucket: VersionedBucket = self._create_bucket(
            bucket_name=api_settings.frontend_data_transfer_bucket_name,
            public_read_access=True,
            role=lambda_role,
            permissions=Permissions.READ_WRITE,
        )
        api_settings.frontend_data_transfer_bucket_name = self._frontend_transfer_bucket.bucket_name
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

    def _create_bucket(
        self,
        bucket_name: str,
        public_read_access: bool,
        role: iam.Role,
        permissions: Permissions,
    ) -> VersionedBucket:
        bucket_name = (bucket_name + self._stack_suffix)[:63]
        config = VersionedBucketConfigModel(
            bucket_name=bucket_name,
            public_read_access=public_read_access,
            removal_policy=self._removal_policy,
            delete_objects_on_bucket_removal=True if self._removal_policy == RemovalPolicy.DESTROY else False,
        )
        bucket: VersionedBucket = VersionedBucket(
            scope=self,
            construct_id=f"{config.bucket_name}-bucket",
            config=config,
        )
        if permissions == Permissions.READ:
            bucket.grant_read_access(role)
        elif permissions == Permissions.READ_WRITE:
            bucket.grant_read_write_access(role)
        else:
            raise ValueError(f"Invalid permissions: {permissions} for bucket {bucket_name}")
        return bucket

    def _create_lambda_function(self, security_group_allowing_db_connections: ec2.SecurityGroup) -> DockerLambda:
        config = self._get_lambda_config(security_group_allowing_db_connections)
        name = config.function_name
        python_lambda: DockerLambda = DockerLambda(
            self,
            construct_id=f"{name}-lambda",
            config=config,
        )
        secrets = [
            self._settings.doc_db_credentials_secret_name,
            self._settings.pinecone_db_api_key_secret_name,
            self._settings.openAI_api_key_secret_name,
        ]
        python_lambda.add_read_only_secrets_manager_access(arns=[get_secret_arn_from_name(secret) for secret in secrets])
        python_lambda.allow_public_invoke_of_function()
        return python_lambda

    def _get_lambda_config(self, security_group_allowing_db_connections: ec2.SecurityGroup) -> BaseLambdaConfigModel:
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
            security_groups=[security_group_secrets, security_group_allowing_db_connections],
            function_url_config=LambdaURLConfigModel(
                allowed_headers=["*"],
                allowed_origins=["*"],
                auth_type=_lambda.FunctionUrlAuthType.NONE,
            ),
            run_as_webserver=True,
            custom_docker_commands=[
                f"RUN mkdir -p {self._settings.nltk_data}",  # Create directory for model
                # punkt and and stopwords are used for pinecone SPLADE
                # averaged_perceptron_tagger is used for langchain for HTML parsing
                # the path is specified as lambda does NOT have access to the default path
                f"RUN python -m nltk.downloader -d {self._settings.nltk_data} punkt stopwords averaged_perceptron_tagger",  # Download the model and save it to the directory
                # poppler-utils is used for the python pdf to image package
                "RUN apt-get update && apt-get install -y poppler-utils wget unzip",
                # install chrome driver for selenium use
                f"RUN wget -O {self._settings.chrome_driver_path}.zip https://chromedriver.storage.googleapis.com/90.0.4430.24/chromedriver_linux64.zip",
                # unzip to the self._settings.chrome_driver_path directory
                f"RUN unzip {self._settings.chrome_driver_path}.zip -d {self._settings.chrome_driver_path}",
                # install extra dependencies for chrome driver
                "RUN apt-get install -y libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 chromium",
            ]
        )
        return lambda_config
