"""Define the search database stack."""
from enum import Enum
import os
from typing import Optional, Any
from constructs import Construct
from loguru import logger
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    Duration,
    aws_ecs as ecs,
    aws_autoscaling as autoscaling,
    aws_elasticloadbalancingv2 as elbv2,
)
from aws_cdk.aws_ecs_patterns import ApplicationLoadBalancedServiceBase
from aws_cdk.aws_ecs import (
    Cluster,
    Ec2TaskDefinition,
    Ec2Service,
    PortMapping,
    ContainerImage,
    ContainerDefinition,
    ScalableTaskCount,
    NetworkMode,
    EcsOptimizedImage,
    AmiHardwareType,
    LogDriver,
    AsgCapacityProvider,
    DeploymentCircuitBreaker,
    PlacementStrategy,
    CapacityProviderStrategy,
)
from aws_cdk.aws_elasticloadbalancingv2 import (
    ApplicationLoadBalancer,
    ApplicationProtocol,
    ApplicationTargetGroup,
)
from aws_cdk.aws_autoscaling import (
    BlockDevice,
    BlockDeviceVolume,
    EbsDeviceVolumeType,
    AutoScalingGroup,
    WarmPool,
)
from aws_cdk.aws_applicationautoscaling import Schedule
from tai_aws_account_bootstrap.stack_helpers import add_tags
from tai_aws_account_bootstrap.stack_config_models import StackConfigBaseModel
from .search_service_settings import DeploymentTaiApiSettings
from ..constructs.construct_config import Permissions
from ..constructs.document_db_construct import (
    DocumentDatabase,
    ElasticDocumentDBConfigModel,
    DocumentDBSettings,
)
from ..constructs.construct_helpers import get_vpc
from ..constructs.pinecone_db_construct import PineconeDatabase
from ..constructs.bucket_construct import VersionedBucket
from ..constructs.customresources.pinecone_db.pinecone_db_custom_resource import PineconeDBSettings
from ..constructs.construct_helpers import (
    get_secret_arn_from_name,
)


DOCKER_FILE_NAME = "Dockerfile.searchservice"
FULLY_QUALIFIED_HANDLER_NAME = "taiservice.searchservice.main:create_app"
CWD = os.getcwd()
PROTOCOL_TO_LISTENER_PORT = {
    ApplicationProtocol.HTTP: 80,
    ApplicationProtocol.HTTPS: 443,
}


class ECSServiceType(str, Enum):
    """Define the ECS service type."""

    NO_GPU = "NO_GPU"
    GPU = "GPU"


class TaiSearchServiceStack(Stack):
    """Define the search service for indexing and searching."""

    def __init__(
        self,
        scope: Construct,
        config: StackConfigBaseModel,
        pinecone_db_settings: PineconeDBSettings,
        doc_db_settings: DocumentDBSettings,
        search_service_settings: DeploymentTaiApiSettings,
        vpc: Any,
    ) -> None:
        """Initialize the search database stack."""
        super().__init__(
            scope=scope,
            id=config.stack_id,
            stack_name=config.stack_name,
            description=config.description,
            env=config.deployment_settings.aws_environment,
            tags=config.tags,
            termination_protection=config.termination_protection,
        )
        self._service_url = None
        self._search_service_settings = search_service_settings
        self._pinecone_db_settings = pinecone_db_settings
        self._doc_db_settings = doc_db_settings
        self._config = config
        self._namer = lambda name: f"{config.stack_name}-{name}"
        self._subnet_type_for_doc_db = ec2.SubnetType.PRIVATE_WITH_EGRESS
        self.vpc = get_vpc(scope=self, vpc=vpc)
        self.document_db = self._get_document_db(doc_db_settings=doc_db_settings)
        self.pinecone_db = self._get_pinecone_db()
        self._security_group_for_connecting_to_doc_db = self.document_db.security_group_for_connecting_to_cluster
        # these needs to occur before creating the search service so that the search service points to the correct bucket
        name_with_suffix = (search_service_settings.cold_store_bucket_name + config.stack_suffix)[:63]
        search_service_settings.doc_db_fully_qualified_domain_name = self.document_db.fully_qualified_domain_name
        search_service_settings.cold_store_bucket_name = name_with_suffix
        self.search_services: list[Ec2Service] = self._get_search_services(self._security_group_for_connecting_to_doc_db)
        self._cold_store_bucket: VersionedBucket = VersionedBucket.create_bucket(
            scope=self,
            bucket_name=search_service_settings.cold_store_bucket_name,
            public_read_access=True,
            permissions=Permissions.READ_WRITE,
            removal_policy=config.removal_policy,
            role=[service.task_definition.task_role for service in self.search_services],
        )
        name_with_suffix = (search_service_settings.documents_to_index_queue + config.stack_suffix)[:63]
        search_service_settings.documents_to_index_queue = name_with_suffix
        self._documents_to_index_queue: VersionedBucket = VersionedBucket.create_bucket(
            scope=self,
            bucket_name=search_service_settings.documents_to_index_queue,
            public_read_access=True,
            permissions=Permissions.READ_WRITE,
            removal_policy=config.removal_policy,
        )
        add_tags(self, config.tags)

    @property
    def security_group_for_connecting_to_doc_db(self) -> ec2.SecurityGroup:
        """
        Return the security group for connecting to the document db.

        If you want to connect to the document db from another stack, you need to use this security group.
        """
        return self._security_group_for_connecting_to_doc_db

    @property
    def documents_to_index_queue(self) -> VersionedBucket:
        """Return the bucket for transferring documents to index."""
        return self._documents_to_index_queue

    @property
    def service_url(self) -> Optional[str]:
        """Return the service url."""
        return self._service_url

    def _get_document_db(self, doc_db_settings: DocumentDBSettings) -> DocumentDatabase:
        db_config = ElasticDocumentDBConfigModel(
            cluster_name=self._doc_db_settings.cluster_name,
            vpc=self.vpc,
            subnet_type=self._subnet_type_for_doc_db,
        )
        db = DocumentDatabase(
            scope=self,
            construct_id=self._namer("document-db"),
            db_setup_settings=doc_db_settings,
            db_config=db_config,
        )
        return db

    def _get_pinecone_db(self) -> PineconeDatabase:
        db = PineconeDatabase(
            scope=self,
            construct_id=self._namer("pinecone-db"),
            db_settings=self._pinecone_db_settings,
            removal_policy=self._config.removal_policy,
        )
        return db

    def _get_search_services(self, sg_for_connecting_to_db: ec2.SecurityGroup) -> list[Ec2Service]:
        target_port = 80
        container_port = 8080
        self._create_docker_file(container_port)
        service: Ec2Service = self._create_ecs_service(container_port, target_port, sg_for_connecting_to_db)
        services = [service]
        self._get_target_group(services, target_port, target_protocol=ApplicationProtocol.HTTP)
        for service in services:
            self._get_scalable_task(service)
        return services

    def _create_ecs_service(
        self,
        container_port: int,
        target_port: int,
        sg_for_connecting_to_db: ec2.SecurityGroup,
    ) -> Ec2Service:
        """Create an ECS service."""
        task_definition: Ec2TaskDefinition = Ec2TaskDefinition(
            self,
            self._namer("task"),
            network_mode=NetworkMode.AWS_VPC,
        )
        task_definition.add_to_task_role_policy(
            statement=iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[get_secret_arn_from_name(secret) for secret in self._search_service_settings.secret_names],
            ),
        )
        cluster, capacity_provider_mapping = self._get_cluster()
        capacity_provider_strategies: list[CapacityProviderStrategy] = []
        for name, service_type in capacity_provider_mapping.items():
            weight = 1 if service_type == ECSServiceType.NO_GPU else 0
            logger.info(f"Adding capacity provider strategy with weight {weight} for capacity provider '{name}'")
            capacity_provider_strategies.append(
                CapacityProviderStrategy(
                    capacity_provider=name,
                    base=0,
                    weight=weight,
                )
            )
        self._get_container_definition(task_definition, container_port)
        security_group = self._get_ec2_security_group(target_port)
        service: Ec2Service = Ec2Service(
            self,
            self._namer("service"),
            service_name=self._namer("service"),
            cluster=cluster,
            min_healthy_percent=50,
            max_healthy_percent=200,
            task_definition=task_definition,
            security_groups=[security_group, sg_for_connecting_to_db],
            circuit_breaker=DeploymentCircuitBreaker(rollback=True),
            placement_strategies=[PlacementStrategy.packed_by_memory()],
            capacity_provider_strategies=capacity_provider_strategies,
            health_check_grace_period=Duration.seconds(450),
        )
        return service

    def _create_docker_file(self, target_port: int) -> None:
        docker_file_path = os.path.join(CWD, DOCKER_FILE_NAME)
        with open(docker_file_path, "w", encoding="utf-8") as f:
            f.write(
                self._search_service_settings.get_docker_file_contents(
                    target_port,
                    FULLY_QUALIFIED_HANDLER_NAME,
                    worker_count=16,
                )
            )

    def _get_cluster(self) -> tuple[Cluster, dict[str, ECSServiceType]]:
        cluster = Cluster(
            self,
            self._namer("cluster"),
            vpc=self.vpc,
        )
        no_gpu_asg = self._get_auto_scaling_group(ECSServiceType.NO_GPU, cluster)
        gpu_asg = self._get_auto_scaling_group(ECSServiceType.GPU, cluster)
        asgs_and_types = [
            (no_gpu_asg, ECSServiceType.NO_GPU),
            (gpu_asg, ECSServiceType.GPU),
        ]
        capacity_provider_mapping = {}
        for asg, service_type in asgs_and_types:
            logger.info(f"Adding {service_type.value} ASG to cluster")
            name = self._namer(f"capacity-provider-{service_type.value}")
            capacity_provider_mapping[name] = service_type
            cluster.add_asg_capacity_provider(
                provider=AsgCapacityProvider(
                    self,
                    name,
                    auto_scaling_group=asg,
                    capacity_provider_name=name,
                    enable_managed_scaling=True,
                    enable_managed_termination_protection=True,
                )
            )
        return cluster, capacity_provider_mapping

    def _get_auto_scaling_group(self, service_type: ECSServiceType, cluster: Cluster) -> AutoScalingGroup:
        block_devices = [
            BlockDevice(
                device_name="/dev/xvda",
                volume=BlockDeviceVolume.ebs(
                    volume_type=EbsDeviceVolumeType.GP3,
                    delete_on_termination=True,
                    volume_size=200,
                ),
            ),
        ]
        user_data = ec2.UserData.for_linux()
        # this is necessary for the warm pool to work with ECS
        user_data.add_commands(f"echo -e 'ECS_WARM_POOLS_CHECK=true' >> /etc/ecs/ecs.config")
        if service_type == ECSServiceType.GPU:
            instance_type = ec2.InstanceType.of(
                instance_class=ec2.InstanceClass.G4DN,
                instance_size=ec2.InstanceSize.XLARGE,
            )
            ami = EcsOptimizedImage.amazon_linux2(hardware_type=AmiHardwareType.GPU)
        else:
            instance_type = ec2.InstanceType.of(
                instance_class=ec2.InstanceClass.R6A,
                instance_size=ec2.InstanceSize.XLARGE2,
            )
            ami = EcsOptimizedImage.amazon_linux2(hardware_type=AmiHardwareType.STANDARD)
        asg = AutoScalingGroup(
            self,
            self._namer(f"asg-{service_type.value}"),
            auto_scaling_group_name=self._namer(f"asg-{service_type.value}"),
            vpc=self.vpc,
            instance_type=instance_type,
            machine_image=ami,
            max_capacity=2,
            min_capacity=0,
            # spot_price="0.35",
            block_devices=block_devices,
            max_instance_lifetime=Duration.days(10),
            user_data=user_data,
            new_instances_protected_from_scale_in=True,
        )
        WarmPool(
            self,
            id=self._namer(f"asg-warm-pool-{service_type.value}"),
            auto_scaling_group=asg,
            reuse_on_scale_in=False,
        )
        return asg

    def _get_container_definition(self, task_definition: Ec2TaskDefinition, container_port: int) -> ContainerDefinition:
        container: ContainerDefinition = task_definition.add_container(
            self._namer("container"),
            image=ContainerImage.from_asset(directory=CWD, file=DOCKER_FILE_NAME),
            environment=self._search_service_settings.dict(for_environment=True, export_aws_vars=True),
            logging=LogDriver.aws_logs(stream_prefix=self._namer("log")),
            gpu_count=0,
            memory_reservation_mib=15000,
            stop_timeout=Duration.seconds(600),
        )
        container.add_port_mappings(
            PortMapping(container_port=container_port),
        )
        return container

    def _get_ec2_security_group(self, target_port: int) -> ec2.SecurityGroup:
        target_sg: ec2.SecurityGroup = ec2.SecurityGroup(
            self,
            self._namer("target-sg"),
            vpc=self.vpc,
            allow_all_outbound=True,
        )
        target_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(target_port),
        )
        return target_sg

    def _get_scalable_task(self, service: Ec2Service) -> ScalableTaskCount:
        min_task_count = 5
        max_task_count = 8
        scaling_task = service.auto_scale_task_count(
            min_capacity=min_task_count,
            max_capacity=max_task_count,
        )
        scaling_task.scale_on_cpu_utilization(
            id=self._namer("task-cpu-scaling"),
            target_utilization_percent=50,
            scale_out_cooldown=Duration.seconds(300),  # we should be fast because of the warm pool
            disable_scale_in=False,
        )
        # for some reason, scaling on multiple metrics prohibits scaling in,
        # scaling out does not appear to be affected
        # scaling_task.scale_on_memory_utilization(
        #     id=self._namer("task-memory-scaling"),
        #     target_utilization_percent=50,
        #     scale_out_cooldown=Duration.seconds(300),  # we should be fast because of the warm pool
        #     disable_scale_in=False,
        # )
        scaling_task.scale_on_schedule(
            id=self._namer("scale-up"),
            schedule=Schedule.cron(hour="14", minute="0", week_day="*"),  # 8am MST
            min_capacity=min_task_count,
            max_capacity=max_task_count,
        )
        scaling_task.scale_on_schedule(
            self._namer("scale-down"),
            schedule=Schedule.cron(hour="5", minute="0", week_day="*"),  # 11pm MST
            min_capacity=1,
            max_capacity=max_task_count,
        )
        return scaling_task

    def _get_target_group(
        self, services: list[Ec2Service], target_port: int, target_protocol: ApplicationProtocol
    ) -> ApplicationTargetGroup:
        alb: ApplicationLoadBalancer = ApplicationLoadBalancer(self, self._namer("alb"), vpc=self.vpc, internet_facing=True)
        self._service_url = alb.load_balancer_dns_name
        listener = alb.add_listener(
            self._namer("listener"),
            port=80,
        )
        target_group = listener.add_targets(
            self._namer("target-group"),
            port=target_port,
            protocol=target_protocol,
            targets=services,
            deregistration_delay=Duration.seconds(600),
            health_check=elbv2.HealthCheck(
                healthy_threshold_count=2,
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                unhealthy_threshold_count=3,
            ),
        )
        return target_group

    def get_search_service_NEW(self, sg_for_connecting_to_db: ec2.SecurityGroup) -> ApplicationLoadBalancedServiceBase:
        alb: ApplicationLoadBalancer = ApplicationLoadBalancer(
            self, id=self._namer("alb"), load_balancer_name=self._namer("alb"), vpc=self.vpc, internet_facing=True
        )
        self._service_url = alb.load_balancer_dns_name
        protocol = ApplicationProtocol.HTTPS
        service = ApplicationLoadBalancedServiceBase(
            scope=self,
            id=self._namer("service"),
            circuit_breaker=DeploymentCircuitBreaker(rollback=True),
            cluster=self._get_cluster(),
            listener_port=PROTOCOL_TO_LISTENER_PORT[protocol],
        )
