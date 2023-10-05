
from constructs import Construct
from typing import Any, Optional, Union
from enum import Enum
from aws_cdk import (
    aws_ec2 as ec2,
    aws_elasticache as elasticache,
)
from pydantic import BaseModel, Field, validator
from .construct_helpers import (
    validate_vpc,
    get_vpc,
    create_restricted_security_group,
)


class NodeType(str, Enum):
    MICRO = "cache.t4g.micro"
    SMALL = "cache.t4g.small"
    MEDIUM = "cache.t4g.medium"
    LARGE = "cache.m7g.large"
    XLARGE = "cache.m7g.xlarge"


class EngineType(str, Enum):
    REDIS = "Redis"


class ElastiCacheConfigModel(BaseModel):
    cluster_name: str = Field(
        ...,
        description="The name of the cluster.",
    )
    cluster_description: str = Field(
        default="",
        description="The description of the cluster.",
    )
    cache_node_type: NodeType = Field(
        default=NodeType.MICRO,
        description="The compute and memory capacity of the nodes in the cluster.",
    )
    engine: EngineType = Field(
        default=EngineType.REDIS,
        description="The name of the cache engine to be used for the cluster.",
    )
    multi_az_enabled: bool = Field(
        default=True,
        description="Specifies whether a cluster is multi-AZ enabled.",
    )
    num_shards: int = Field(
        ...,
        ge=1,
        le=10,
        description="The number of cache nodes that the cluster should have.",
    )
    replicas_per_shard: int = Field(
        default=1,
        ge=0,
        le=5,
        description="The number of replicas per shard.",
    )
    subnet_type: ec2.SubnetType = Field(
        default=ec2.SubnetType.PRIVATE_ISOLATED,
        description="The type of subnets to use for the cluster.",
    )
    preferred_maintenance_window: str = Field(
        default="sun:05:00-sun:06:00",
        description="Specifies the weekly time range during which maintenance on the cluster is performed.",
    )
    vpc: Any = Field(
        ...,
        description="The VPC to use for the cluster.",
    )
    security_groups: list[ec2.SecurityGroup] = Field(
        default_factory=list,
        description="The security groups to use for the cluster.",
    )
    cluster_port: int = Field(
        default=6379,
        description="The port number of the cluster.",
    )

    class Config:
        """Define the Pydantic model configuration."""

        arbitrary_types_allowed = True

    @validator("num_shards")
    def validate_num_cache_nodes(cls, num_cache_nodes: int, values: dict) -> int:
        if values["multi_az_enabled"]:
            assert num_cache_nodes >= 2, "The number of cache nodes must be even when multi-AZ is enabled."
        return num_cache_nodes

    @validator("vpc")
    def validate_vpc(cls, vpc) -> Optional[Union[ec2.IVpc, str]]:
        """Validate the VPC."""
        return validate_vpc(vpc)


class ElastiCache(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        db_config: ElastiCacheConfigModel,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)
        self._namer = lambda name: f"{db_config.cluster_name}-{name}"
        db_config.vpc = get_vpc(self, db_config.vpc)
        self._config = db_config
        self._configure_security_groups()
        self._cluster = self._create_cluster()

    @property
    def security_group_for_connecting_to_cluster(self) -> ec2.SecurityGroup:
        return self._security_group_for_connecting_to_cluster

    @property
    def cluster(self) -> elasticache.CfnReplicationGroup:
        return self._cluster

    @property
    def fully_qualified_domain_name(self) -> str:
        return self._cluster.attr_configuration_end_point_address

    @property
    def port(self) -> str:
        return self._cluster.attr_configuration_end_point_port

    def _configure_security_groups(self) -> None:
        self._db_security_group = create_restricted_security_group(
            scope=self,
            name=self._namer("cluster"),
            description=f"The security group for the {self._config.cluster_name} {self._config.engine} cluster.",
            vpc=self._config.vpc,
        )
        self._config.security_groups.append(self._db_security_group)
        self._security_group_for_connecting_to_cluster = create_restricted_security_group(
            scope=self,
            name=self._namer("connecting-to-db"),
            description=f"The security group for connecting to the {self._config.cluster_name} {self._config.engine} cluster.",
            vpc=self._config.vpc,
        )
        self._db_security_group.add_ingress_rule(
            peer=self._security_group_for_connecting_to_cluster,
            connection=ec2.Port.tcp(self._config.cluster_port),
            description="Allow inbound connections from the security group for connecting to the cluster.",
        )

    def _get_selected_subnets(self) -> ec2.SelectedSubnets:
        vpc: ec2.IVpc = self._config.vpc
        selected_subnets = vpc.select_subnets(subnet_type=self._config.subnet_type)
        num_subnets = len(selected_subnets.subnets)
        azs = set()
        for subnet in selected_subnets.subnets:
            azs.add(subnet.availability_zone)
        assert len(azs) >= num_subnets, "The subnets must be in different AZs."
        return selected_subnets

    def _get_subnet_group(self) -> elasticache.CfnSubnetGroup:
        subnet_group = elasticache.CfnSubnetGroup(
            self,
            self._namer("subnet-group"),
            description=f"Subnet group for the {self._config.cluster_name} cluster.",
            subnet_ids=self._get_selected_subnets().subnet_ids,
        )
        return subnet_group

    def _create_cluster(self) -> elasticache.CfnReplicationGroup:
        if self._config.engine == EngineType.REDIS:
            return self._create_redis_cluster()
        raise NotImplementedError(f"Engine {self._config.engine} is not supported.")

    def _create_redis_cluster(self) -> elasticache.CfnReplicationGroup:
        sg_ids = [security_group.security_group_id for security_group in self._config.security_groups]
        cluster = elasticache.CfnReplicationGroup(
            self,
            self._namer("cluster"),
            replication_group_description=self._config.cluster_description,
            automatic_failover_enabled=True,
            auto_minor_version_upgrade=True,
            cache_node_type=self._config.cache_node_type,
            cache_subnet_group_name=self._get_subnet_group().ref,
            cluster_mode='enabled',
            engine=self._config.engine,
            multi_az_enabled=self._config.multi_az_enabled,
            num_node_groups =self._config.num_shards,
            port=self._config.cluster_port,
            preferred_maintenance_window=self._config.preferred_maintenance_window,
            replicas_per_node_group=self._config.replicas_per_shard,
            replication_group_id=self._config.cluster_name,
            security_group_ids=sg_ids,
            transit_encryption_enabled=True,
            transit_encryption_mode="preferred",
        )
        return cluster
