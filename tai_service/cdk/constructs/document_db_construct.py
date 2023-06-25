"""Define the DocumentDB construct."""
from pathlib import Path
from enum import Enum
from typing import Optional, Union, List
from constructs import Construct
from pydantic import BaseModel, Field, root_validator, validator
from aws_cdk import (
    aws_ec2 as ec2,
    aws_docdbelastic as docdb_elastic,
    aws_docdb as docdb,
    aws_iam as iam,
    custom_resources as cr,
    CustomResource,
    Duration,
    Size as StorageSize,
    aws_lambda as _lambda,
)
from .construct_helpers import (
    validate_vpc,
    get_hash_for_all_files_in_dir,
    retrieve_secret,
    get_secret_arn_from_name,
    get_vpc,
    create_restricted_security_group,
)
from .python_lambda_construct import (
    PythonLambda,
    PythonLambdaConfigModel,
)
from .customresources.document_db.document_db_custom_resource import DocumentDBSettings, RuntimeDocumentDBSettings
# This schema is defined by aws documentation for AWS Elastic DocumentDB
# (https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_docdbelastic/CfnCluster.html)
VALID_ADMIN_USERNAME_PATTERN = r"^(?!(admin|root|master|user|username|dbuser|dbadmin|dbroot|dbmaster)$)[a-zA-Z][a-zA-Z0-9]{0,62}$"
VALID_ADMIN_PASSWORD_PATTERN = r"^[a-zA-Z0-9!#$%&*+=?._-]{8,100}$"
VALID_CLUSTER_NAME_PATTERN = r"^[a-z][a-z0-9-]{0,62}$"
VALID_SHARD_CAPACITIES = {2, 4, 8, 16, 32, 64}
VALID_SHARD_COUNT_RANGE = range(1, 33)
VALID_DAYS_OF_THE_WEEK = r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)'
MINIMUM_SUBNETS_FOR_DOCUMENT_DB = 3
# Format: ddd:hh24:mi-ddd:hh24:mi
VALID_MAINTENANCE_WINDOW_PATTERN =  fr'^{VALID_DAYS_OF_THE_WEEK}\:([01]\d|2[0-3])\:[0-5]\d\-([A-Z][a-z]{2})\:([01]\d|2[0-3])\:[0-5]\d$'
CONSTRUCTS_DIR = Path(__file__).parent
DOCUMENT_DB_CUSTOM_RESOURCE_DIR = CONSTRUCTS_DIR / "customresources" / "document_db"

class AuthType(str, Enum):
    """Define the authentication type for the DocumentDB cluster."""

    PLAINTEXT_PASSWORD = "PLAIN_TEXT"
    SECRET_ARN_PASSWORD = "SECRET_ARN"


class ElasticDocumentDBConfigModel(BaseModel):
    """Define the configuration for the ElasticDB construct."""

    cluster_name: str = Field(
        ...,
        description="The name of the DocumentDB cluster. Note, this is not the fully qualified domain name.",
        regex=VALID_CLUSTER_NAME_PATTERN,
    )
    auth_type: AuthType = Field(
        default=AuthType.PLAINTEXT_PASSWORD,
        const=True,
        description="The authentication type for the DocumentDB cluster.",
    )
    shard_count: int = Field(
        default=1,
        description="The number of shards to create in the cluster.",
        ge=VALID_SHARD_COUNT_RANGE.start,
        le=VALID_SHARD_COUNT_RANGE.stop,
    )
    shard_capacity: int = Field(
        default=2,
        description="The capacity of each shard in the cluster.",
    )
    maintenance_window: str = Field(
        default="Mon:00:00-Mon:01:00",
        description=f"The maintenance window for the cluster. Format: {VALID_MAINTENANCE_WINDOW_PATTERN}",
        regex=VALID_MAINTENANCE_WINDOW_PATTERN,
    )
    vpc: Union[ec2.Vpc, str] = Field(
        ...,
        description="The VPC to use for the cluster.",
    )
    subnet_type: ec2.SubnetType = Field(
        default=ec2.SubnetType.PRIVATE_ISOLATED,
        description="The subnet type to use for the cluster.",
    )
    security_groups: Optional[list[ec2.SecurityGroup]] = Field(
        default=[],
        description="The security groups to use for the cluster.",
    )

    class Config:
        """Define the Pydantic model configuration."""

        arbitrary_types_allowed = True

    @root_validator
    def validate_secret_arn_password(cls, values) -> dict:
        """Validate that if the auth_type is SECRET_ARN_PASSWORD, the admin_password is not None."""
        if values["auth_type"] == AuthType.SECRET_ARN_PASSWORD and values["admin_password"] is None:
            raise ValueError(f"Must define admin_password when auth_type is {AuthType.SECRET_ARN_PASSWORD}")
        return values

    @validator("shard_capacity")
    def validate_shard_capacity(cls, shard_capacity: int) -> int:
        """Validate the shard capacity."""
        if shard_capacity in VALID_SHARD_CAPACITIES:
            return shard_capacity
        raise ValueError(f"shard_capacity must be one of {VALID_SHARD_CAPACITIES}. You provided {shard_capacity}")

    @validator("vpc")
    def validate_vpc(cls, vpc) -> Optional[Union[ec2.IVpc, str]]:
        """Validate the VPC."""
        return validate_vpc(vpc)


class DocumentDBConfigModel(BaseModel):
    """Define the configuration for the DocumentDB construct."""


class DocumentDatabase(Construct):
    """Define the DocumentDB construct."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        db_setup_settings: DocumentDBSettings,
        db_config: Union[DocumentDBConfigModel, ElasticDocumentDBConfigModel],
        **kwargs,
    ) -> None:
        """Initialize the DocumentDB construct."""
        super().__init__(scope, construct_id, **kwargs)
        self._namer = lambda x: f"{db_config.cluster_name}-{x}"
        db_config.vpc = get_vpc(self, db_config.vpc)
        self._config = db_config
        self._settings = db_setup_settings
        self.security_group = create_restricted_security_group(
            name=self._namer("cluster-sg"),
            description="The security group for the DocumentDB cluster.",
            vpc=self._config.vpc,
        )
        self.security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(self._settings.cluster_port),
            description="Allow traffic from any IP address.",
        )
        self._config.security_groups.append(self.security_group)
        self.db_cluster = self._create_cluster()
        self.custom_resource = self._create_custom_resource()
        self.custom_resource.node.add_dependency(self.db_cluster)

    def _add_security_group_rules_for_cluster(self) -> None:
        """Add the security group rules for the cluster."""
        self.security_group.add_ingress_rule(
            peer=self.security_group,
            connection=ec2.Port.tcp(self._settings.cluster_port),
            description="Allow traffic from the VPC.",
        )

    def _create_cluster(self) -> Union[docdb_elastic.CfnCluster, docdb.DatabaseCluster]:
        """Create the DocumentDB cluster."""
        if isinstance(self._config, DocumentDBConfigModel):
            return self._create_standard_cluster()
        return self._create_elastic_cluster()

    def _create_standard_cluster(self) -> docdb.DatabaseCluster:
        raise NotImplementedError("Standard clusters are not yet supported.")

    def _create_elastic_cluster(self) -> docdb_elastic.CfnCluster:
        """Create the DocumentDB cluster."""
        admin_password = retrieve_secret(self._settings.admin_user_password_secret_name)
        cluster = docdb_elastic.CfnCluster(
            self,
            id=self._namer("cluster"),
            cluster_name=self._config.cluster_name,
            admin_user_name=self._settings.admin_username,
            admin_user_password=admin_password,
            auth_type=self._config.auth_type.value,
            shard_count=self._config.shard_count,
            shard_capacity=self._config.shard_capacity,
            preferred_maintenance_window=self._config.maintenance_window,
            subnet_ids=[subnet.subnet_id for subnet in self._get_selected_subnets().subnets],
            vpc_security_group_ids=[security_group.security_group_id for security_group in self._config.security_groups],
        )
        return cluster

    def _get_selected_subnets(self) -> ec2.SelectedSubnets:
        selected_subnets = self._config.vpc.select_subnets(subnet_type=self._config.subnet_type)
        assert len(selected_subnets.subnets) >= MINIMUM_SUBNETS_FOR_DOCUMENT_DB,\
            f"VPC must have at least {MINIMUM_SUBNETS_FOR_DOCUMENT_DB} subnets. The VPC provided only "\
                f"has {len(selected_subnets.subnets)} subnets."
        return selected_subnets

    def _create_custom_resource(self) -> cr.Provider:
        config = self._get_lambda_config()
        name = config.function_name
        lambda_function = PythonLambda.get_lambda_function(
            self,
            construct_id=f"custom-resource-lambda-{name}",
            config=config,
        )
        self._add_secrets_to_lambda_role(lambda_function)
        provider: cr.Provider = cr.Provider(
            self,
            id="custom-resource-provider",
            on_event_handler=lambda_function,
            provider_function_name=name + "-PROVIDER",
        )
        custom_resource = CustomResource(
            self,
            id="custom-resource",
            service_token=provider.service_token,
            properties={"hash": get_hash_for_all_files_in_dir(CONSTRUCTS_DIR)},
        )
        return custom_resource

    def _add_secrets_to_lambda_role(self, lambda_function: _lambda.Function) -> None:
        """Add the secrets to the lambda role."""
        secret_arns = []
        for user in self._settings.user_config:
            arn = get_secret_arn_from_name(user.password_secret_name)
            secret_arns.append(arn)
        secret_arns.append(get_secret_arn_from_name(self._settings.admin_user_password_secret_name))
        lambda_function.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                effect=iam.Effect.ALLOW,
                resources=secret_arns,
            )
        )

    def _get_lambda_config(self) -> PythonLambdaConfigModel:
        runtime_settings = RuntimeDocumentDBSettings(
            cluster_host_name=self.db_cluster.attr_cluster_endpoint,
            **self._settings.dict(),
        )
        security_group = create_restricted_security_group(
            name=self._namer("lambda-sg"),
            description="The security group for the DocumentDB lambda.",
            vpc=self._config.vpc,
        )
        ec2.InterfaceVpcEndpoint(
            self,
            id="lambda-secrets-manager-endpoint",
            vpc=self._config.vpc,
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            security_groups=[security_group],
            subnets=ec2.SubnetSelection(subnet_type=self._config.subnet_type),
        )
        lambda_config = PythonLambdaConfigModel(
            function_name="document-db-custom-resource",
            description="Custom resource for performing CRUD operations on the document database",
            code_path=DOCUMENT_DB_CUSTOM_RESOURCE_DIR,
            handler_module_name="main",
            handler_name="lambda_handler",
            runtime_environment=runtime_settings,
            requirements_file_path=DOCUMENT_DB_CUSTOM_RESOURCE_DIR / "requirements.txt",
            files_to_copy_into_handler_dir=[
                CONSTRUCTS_DIR / "construct_config.py",
                DOCUMENT_DB_CUSTOM_RESOURCE_DIR.parent / "custom_resource_interface.py",
            ],
            timeout=Duration.minutes(3),
            memory_size=128,
            ephemeral_storage_size=StorageSize.mebibytes(512),
            vpc=self._config.vpc,
            subnet_selection=ec2.SubnetSelection(subnet_type=self._config.subnet_type),
            security_groups=[security_group, self.security_group],
        )
        return lambda_config
