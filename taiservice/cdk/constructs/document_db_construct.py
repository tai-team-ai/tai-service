"""Define the DocumentDB construct."""
from pathlib import Path
from enum import Enum
from typing import Any, Optional, Union, List
from constructs import Construct
from pydantic import BaseModel, Field, root_validator, validator
from aws_cdk import (
    aws_ec2 as ec2,
    aws_docdbelastic as docdb_elastic,
    aws_docdb as docdb,
    custom_resources as cr,
    CustomResource,
    Duration,
    Size as StorageSize,
    RemovalPolicy,
    SecretValue,
)
from .construct_helpers import (
    validate_vpc,
    get_hash_for_all_files_in_dir,
    retrieve_secret,
    get_secret_arn_from_name,
    get_vpc,
    create_restricted_security_group,
    vpc_interface_exists,
)
from .lambda_construct import (
    PythonLambda,
    BaseLambdaConfigModel,
)
from .customresources.document_db.settings import DocumentDBSettings, RuntimeDocumentDBSettings
# This schema is defined by aws documentation for AWS Elastic DocumentDB
# (https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_docdbelastic/CfnCluster.html)
VALID_ADMIN_USERNAME_PATTERN = r"^(?!(admin|root|master|user|username|dbuser|dbadmin|dbroot|dbmaster)$)[a-zA-Z][a-zA-Z0-9]{0,62}$"
VALID_ADMIN_PASSWORD_PATTERN = r"^[a-zA-Z0-9!#$%&*+=?._-]{8,100}$"
VALID_CLUSTER_NAME_PATTERN = r"^[a-z][a-z0-9-]{0,62}$"
VALID_SHARD_CAPACITIES = {2, 4, 8, 16, 32, 64}
VALID_SHARD_COUNT_RANGE = range(1, 33)
VALID_DAYS_OF_THE_WEEK = r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)'
MINIMUM_SUBNETS_FOR_DOCUMENT_DB = 2
MAXIMUM_SUBNETS_FOR_DOCUMENT_DB = 6
# Format: ddd:hh24:mi-ddd:hh24:mi
VALID_MAINTENANCE_WINDOW_PATTERN =  fr'^{VALID_DAYS_OF_THE_WEEK}\:([01]\d|2[0-3])\:[0-5]\d\-([A-Z][a-z]{2})\:([01]\d|2[0-3])\:[0-5]\d$'
CONSTRUCTS_DIR = Path(__file__).parent
DOCUMENT_DB_CUSTOM_RESOURCE_DIR = CONSTRUCTS_DIR / "customresources" / "document_db"

class AuthType(str, Enum):
    """Define the authentication type for the DocumentDB cluster."""

    PLAINTEXT_PASSWORD = "PLAIN_TEXT"
    SECRET_ARN_PASSWORD = "SECRET_ARN"


class BaseDocumentDBConfigModel(BaseModel):
    """Define the base configuration for the DocumentDB construct."""

    cluster_name: str = Field(
        ...,
        description="The name of the DocumentDB cluster. Note, this is not the fully qualified domain name.",
        regex=VALID_CLUSTER_NAME_PATTERN,
    )
    shard_count: int = Field(
        default=1,
        description="The number of shards to create in the cluster.",
        ge=VALID_SHARD_COUNT_RANGE.start,
        le=VALID_SHARD_COUNT_RANGE.stop,
    )
    maintenance_window: str = Field(
        default="Mon:00:00-Mon:01:00",
        description=f"The maintenance window for the cluster. Format: {VALID_MAINTENANCE_WINDOW_PATTERN}",
        regex=VALID_MAINTENANCE_WINDOW_PATTERN,
    )
    vpc: Any = Field(
        ...,
        description="The VPC to use for the cluster.",
    )
    subnet_type: ec2.SubnetType = Field(
        default=ec2.SubnetType.PRIVATE_ISOLATED,
        description="The subnet type to use for the cluster.",
    )
    security_groups: list[ec2.SecurityGroup] = Field(
        default_factory=list,
        description="The security groups to use for the cluster.",
    )

    class Config:
        """Define the Pydantic model configuration."""

        arbitrary_types_allowed = True

    @validator("vpc")
    def validate_vpc(cls, vpc) -> Optional[Union[ec2.IVpc, str]]:
        """Validate the VPC."""
        return validate_vpc(vpc)


class ElasticDocumentDBConfigModel(BaseDocumentDBConfigModel):
    """Define the configuration for the ElasticDB construct."""

    auth_type: AuthType = Field(
        default=AuthType.PLAINTEXT_PASSWORD,
        const=True,
        description="The authentication type for the DocumentDB cluster.",
    )
    shard_capacity: int = Field(
        default=2,
        description="The capacity of each shard in the cluster.",
    )

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



class InstanceType(str, Enum):
    """Define valid instance types for the DocumentDB cluster."""
    MICRO = "t4g.medium"
    SMALL = "t3.medium"
    MEDIUM = "r6g.large"
    LARGE = "r6g.xlarge"


class DocumentDBConfigModel(BaseDocumentDBConfigModel):
    """Define the configuration for the DocumentDB construct."""
    instance_type: InstanceType = Field(
        default=InstanceType.SMALL,
        description="The instance type to use."
    )
    deletion_protection: bool = Field(
        default=True,
        description="Indicates whether the DB cluster has deletion protection enabled."
    )
    enable_performance_insights: bool = Field(
        default=False,
        description="Indicates whether Performance Insights is enabled for the DB instance."
    )
    removal_policy: Optional[RemovalPolicy] = Field(
        default=None,
        description="The AWS CDK RemovalPolicy to apply to the DB Cluster."
    )


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
        self._configure_security_groups()
        self._db_cluster = self._create_cluster()
        self.custom_resource = self._create_custom_resource()
        self.custom_resource.node.add_dependency(self.db_cluster)

    @property
    def db_security_group(self) -> ec2.SecurityGroup:
        """Return the security group for the DocumentDB cluster."""
        return self._db_security_group

    @property
    def security_group_for_connecting_to_cluster(self) -> ec2.SecurityGroup:
        """
        Return the security group for connecting to the DocumentDB cluster.

        If you want to connect to the DocumentDB cluster, you must add your IP address to this security group.
        """
        return self._security_group_for_connecting_to_cluster

    @property
    def db_cluster(self) -> Union[docdb_elastic.CfnCluster, docdb.DatabaseCluster]:
        """Return the DocumentDB cluster."""
        return self._db_cluster

    @property
    def fully_qualified_domain_name(self) -> str:
        """Return the fully qualified domain name for the DocumentDB cluster."""
        if isinstance(self._db_cluster, docdb.DatabaseCluster):
            return self._db_cluster.cluster_endpoint.hostname
        return self._db_cluster.attr_cluster_endpoint

    @property
    def access_port(self) -> int:
        """Return the port to use for accessing the DocumentDB cluster."""
        return self._settings.cluster_port

    def _configure_security_groups(self) -> None:
        self._db_security_group = create_restricted_security_group(
            scope=self,
            name=self._namer("cluster"),
            description="Security group defining inbound connections for the document database.",
            vpc=self._config.vpc,
        )
        self._config.security_groups.append(self._db_security_group)
        self._security_group_for_connecting_to_cluster = create_restricted_security_group(
            scope=self,
            name=self._namer("connecting-to-db"),
            description="The security group for connecting to the DocumentDB cluster.",
            vpc=self._config.vpc,
        )
        self._db_security_group.add_ingress_rule(
            peer=self._security_group_for_connecting_to_cluster,
            connection=ec2.Port.tcp(self._settings.cluster_port),
            description="Allow inbound connections from the security group for connecting to the DocumentDB cluster.",
        )
        self._security_group_for_connecting_to_cluster.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(self._settings.cluster_port),
            description="Allow outbound connections to the DocumentDB cluster.",
        )

    def _create_cluster(self) -> Union[docdb_elastic.CfnCluster, docdb.DatabaseCluster]:
        """Create the DocumentDB cluster."""
        if isinstance(self._config, DocumentDBConfigModel):
            return self._create_standard_cluster(self._config)
        elif isinstance(self._config, ElasticDocumentDBConfigModel):
            return self._create_elastic_cluster(self._config)
        raise ValueError(f"Invalid config type: {type(self._config)}")

    def _create_standard_cluster(self, config: DocumentDBConfigModel) -> docdb.DatabaseCluster:
        """Create the DocumentDB (standard) cluster."""
        
        admin_secret_json = retrieve_secret(self._settings.secret_name)
        username = admin_secret_json[self._settings.username_secret_field_name]

        cluster = docdb.DatabaseCluster(
            self,
            id=self._namer("cluster"),
            instance_type=ec2.InstanceType(config.instance_type),
            master_user=docdb.Login(
                username=username,
                password=SecretValue.secrets_manager(
                    secret_id=self._settings.secret_name,
                    json_field=self._settings.password_secret_field_name,
                ),
            ),
            vpc=config.vpc,
            db_cluster_name=config.cluster_name,
            deletion_protection=config.deletion_protection,
            enable_performance_insights=config.enable_performance_insights,
            instances=config.shard_count,
            port=self._settings.cluster_port,
            preferred_maintenance_window=config.maintenance_window,
            removal_policy=config.removal_policy,
            security_group=self._db_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type=config.subnet_type),
        )
        return cluster

    def _create_elastic_cluster(self, config: ElasticDocumentDBConfigModel) -> docdb_elastic.CfnCluster:
        """Create the DocumentDB cluster."""
        admin_secret_json = retrieve_secret(self._settings.secret_name)
        username = admin_secret_json[self._settings.username_secret_field_name]
        admin_password = admin_secret_json[self._settings.password_secret_field_name]
        subnet_ids = [subnet.subnet_id for subnet in self._get_selected_subnets().subnets]
        cluster = docdb_elastic.CfnCluster(
            self,
            id=self._namer("cluster"),
            cluster_name=config.cluster_name,
            admin_user_name=username,
            admin_user_password=admin_password,
            auth_type=config.auth_type.value,
            shard_count=config.shard_count,
            shard_capacity=config.shard_capacity,
            preferred_maintenance_window=self._config.maintenance_window,
            subnet_ids=subnet_ids,
            vpc_security_group_ids=[security_group.security_group_id for security_group in config.security_groups],
        )
        return cluster

    def _get_selected_subnets(self) -> ec2.SelectedSubnets:
        selected_subnets = self._config.vpc.select_subnets(subnet_type=self._config.subnet_type)
        num_subnets = len(selected_subnets.subnets)
        default_msg = f"The VPC has {num_subnets} subnets of type {self._config.subnet_type}."
        assert num_subnets >= MINIMUM_SUBNETS_FOR_DOCUMENT_DB,\
            f"VPC must have at least {MINIMUM_SUBNETS_FOR_DOCUMENT_DB} subnets. " + default_msg
        assert num_subnets <= MAXIMUM_SUBNETS_FOR_DOCUMENT_DB,\
            f"VPC must have at most {MAXIMUM_SUBNETS_FOR_DOCUMENT_DB} subnets. " + default_msg
        azs = set()
        for subnet in selected_subnets.subnets:
            azs.add(subnet.availability_zone)
        assert len(azs) == num_subnets, "The subnets must be in different AZs."
        return selected_subnets

    def _create_custom_resource(self) -> CustomResource:
        config = self._get_lambda_config()
        name = config.function_name
        lambda_construct: PythonLambda = PythonLambda(
            scope=self,
            construct_id=f"custom-resource-lambda-{name}",
            config=config,
        )
        secret_arns = []
        for user in self._settings.user_config:
            arn = get_secret_arn_from_name(user.secret_name)
            secret_arns.append(arn)
        secret_arns.append(get_secret_arn_from_name(self._settings.secret_name))
        lambda_construct.add_read_only_secrets_manager_access(secret_arns)
        provider: cr.Provider = cr.Provider(
            self,
            id="custom-resource-provider",
            on_event_handler=lambda_construct.lambda_function,
            provider_function_name=name + "-PROVIDER",
        )
        custom_resource = CustomResource(
            self,
            id="custom-resource",
            service_token=provider.service_token,
            properties={"hash": get_hash_for_all_files_in_dir(CONSTRUCTS_DIR)},
        )
        return custom_resource

    def _get_lambda_config(self) -> BaseLambdaConfigModel:
        runtime_settings = RuntimeDocumentDBSettings(
            cluster_host_name=self.fully_qualified_domain_name,
            **self._settings.dict(),
        )
        security_group = create_restricted_security_group(
            scope=self,
            name=self._namer("lambda"),
            description="The security group for the DocumentDB custom resource lambda.",
            vpc=self._config.vpc,
        )
        security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow outbound HTTPS traffic to Secrets Manager.",
        )
        assert vpc_interface_exists(ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER, self._config.vpc),\
            "The VPC must have an interface endpoint for Secrets Manager."
        name = "document-db-custom-resource-" + self._config.cluster_name
        lambda_config = BaseLambdaConfigModel(
            function_name=name,
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
            timeout=Duration.seconds(60),
            memory_size=128,
            ephemeral_storage_size=StorageSize.mebibytes(512),
            vpc=self._config.vpc,
            subnet_selection=ec2.SubnetSelection(subnet_type=self._config.subnet_type),
            security_groups=[security_group, self._security_group_for_connecting_to_cluster],
        )
        return lambda_config
