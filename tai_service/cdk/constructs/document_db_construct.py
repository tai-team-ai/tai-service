"""Define the DocumentDB construct."""

from enum import Enum
from typing import Optional, Union
from constructs import Construct
from pydantic import BaseModel, Field, root_validator, validator
from aws_cdk import (
    aws_ec2 as ec2,
    aws_docdbelastic as docdb_elastic,
    aws_docdb as docdb,
    aws_iam as iam,
    Environment,
    CustomResource,
)
from tai_service.cdk.constructs.construct_helpers import validate_vpc
from tai_service.cdk.constructs.python_lambda_props_builder import PythonLambdaPropsBuilder, PythonLambdaPropsBuilderConfigModel

# This schema is defined by aws documentation for AWS Elastic DocumentDB
# (https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_docdbelastic/CfnCluster.html)
VALID_ADMIN_USERNAME_PATTERN = r"^(?!(admin|root|master|user|username|dbuser|dbadmin|dbroot|dbmaster)$)[a-zA-Z][a-zA-Z0-9]{0,62}$"
VALID_CLUSTER_NAME_PATTERN = r"^[a-z][a-z0-9-]{0,62}$"
VALID_SHARD_CAPACITIES = {2, 4, 8, 16, 32, 64}
VALID_SHARD_COUNT_RANGE = range(1, 33)
VALID_DAYS_OF_THE_WEEK = r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)'
# Format: ddd:hh24:mi-ddd:hh24:mi
VALID_MAINTENANCE_WINDOW_PATTERN =  fr'^{VALID_DAYS_OF_THE_WEEK}\:([01]\d|2[0-3])\:[0-5]\d\-([A-Z][a-z]{2})\:([01]\d|2[0-3])\:[0-5]\d$'
VALID_SECRET_ARN_PATTERN = r'^arn:aws:secretsmanager:[a-z]{2}-[a-z]{4,9}-\d{1}:\d{12}:secret:[a-zA-Z0-9_-]{1,64}\/[a-zA-Z0-9_-]{1,64}\/[a-zA-Z0-9_-]{1,64}$'

class AuthType(str, Enum):
    """Define the authentication type for the DocumentDB cluster."""

    PLAINTEXT_PASSWORD = "PLAIN_TEXT"
    SECRET_ARN_PASSWORD = "SECRET_ARN"


class ElasticDocumentDBConfigModel(BaseModel):
    """Define the configuration for the ElasticDB construct."""

    cluster_name: str = Field(
        ...,
        description="The name of the DocumentDB cluster.",
        regex=VALID_CLUSTER_NAME_PATTERN,
    )
    admin_username: str = Field(
        ...,
        description="The username for the admin user.",
        regex=VALID_ADMIN_USERNAME_PATTERN,
    )
    admin_password: Optional[str] = Field(
        default=None,
        description="The password for the admin user.",
    )
    auth_type: AuthType = Field(
        default=AuthType.PLAINTEXT_PASSWORD,
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
        in_=VALID_SHARD_CAPACITIES,
    )
    maintenance_window: str = Field(
        default="Mon:00:00-Mon:01:00",
        description=f"The maintenance window for the cluster. Format: {VALID_MAINTENANCE_WINDOW_PATTERN}",
        regex=VALID_MAINTENANCE_WINDOW_PATTERN,
    )
    database_password_secret_arn: str = Field(
        ...,
        description="The name of the secret to create for the database.",
        regex=VALID_SECRET_ARN_PATTERN,
    )
    vpc: Union[ec2.IVpc, str] = Field(
        ...,
        description="The VPC to use for the cluster.",
    )
    subnets: ec2.SubnetType = Field(
        default=ec2.SubnetType.PRIVATE_ISOLATED,
        description="The subnet type to use for the cluster.",
    )
    security_groups: Optional[list[ec2.ISecurityGroup]] = Field(
        default=None,
        description="The security groups to use for the cluster.",
    )
    tags: Optional[dict[str, str]] = Field(
        default=None,
        description="The tags to apply to the cluster.",
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
        db_config: Union[DocumentDBConfigModel, ElasticDocumentDBConfigModel],
        lambda_config: PythonLambdaPropsBuilderConfigModel,
        **kwargs,
    ) -> None:
        """Initialize the DocumentDB construct."""
        super().__init__(scope, construct_id, **kwargs)
        self._namer = lambda x: f"{db_config.cluster_name}-{x}"
        self._config = db_config
        self._lambda_config = lambda_config
        self.security_group = self._create_security_group()
        self._config.security_groups.append(self.security_group)
        self.db_cluster = self._create_cluster()
        self.custom_resource = self._create_custom_resource()
        self.custom_resource.node.add_dependency(self.db_cluster)

    def _create_security_group(self) -> ec2.SecurityGroup:
        """Create the security groups for the cluster."""
        name = self._namer("security-group")
        security_group = ec2.SecurityGroup(
            self,
            id=name,
            security_group_name=name,
            description=f"Security group for the DocumentDB cluster {self._config.cluster_name}",
            vpc=self._config.vpc,
        )
        security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow outbound HTTPS traffic for the lambda function to access secrets manager.",
        )
        return security_group

    def _create_cluster(self) -> Union[docdb_elastic.CfnCluster, docdb.DatabaseCluster]:
        """Create the DocumentDB cluster."""
        if isinstance(self._config, DocumentDBConfigModel):
            return self._create_standard_cluster()
        return self._create_elastic_cluster()

    def _create_standard_cluster(self) -> docdb.DatabaseCluster:
        raise NotImplementedError("Standard clusters are not yet supported.")

    def _create_elastic_cluster(self) -> docdb_elastic.CfnCluster:
        """Create the DocumentDB cluster."""
        selected_subnets = self._config.vpc.select_subnets(subnet_type=self._config.subnets)
        cluster = docdb_elastic.CfnCluster(
            self,
            id=self._namer("cluster"),
            cluster_name=self._config.cluster_name,
            admin_user_name=self._config.admin_username,
            admin_user_password=self._config.admin_password,
            auth_type=self._config.auth_type.value,
            shard_count=self._config.shard_count,
            shard_capacity=self._config.shard_capacity,
            preferred_maintenance_window=self._config.maintenance_window,
            subnet_ids=[subnet.subnet_id for subnet in selected_subnets.subnets],
            vpc_security_group_ids=[security_group.security_group_id for security_group in self._config.security_groups],
            tags=self._config.tags,
        )
        return cluster

    def _create_custom_resource(self) -> CustomResource:
        lambda_function = PythonLambdaPropsBuilder.get_lambda_function(
            self,
            construct_id=self._namer("custom-resource-db-initializer-lambda"),
            config=self._lambda_config,
        )
        lambda_function.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                effect=iam.Effect.ALLOW,
                resources=[self._config.database_secret_arn],
            )
        )
        custom_resource = CustomResource(
            self,
            id=self._namer("custom-resource"),
            service_token=lambda_function.function_arn,
        )
        return custom_resource
