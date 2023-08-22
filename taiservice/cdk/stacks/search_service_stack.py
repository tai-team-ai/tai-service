"""Define the search database stack."""
from enum import Enum
import os
from typing import Optional, Any
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    Duration,
)
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
    Schedule,
    Signals,
)
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


DOCKER_FILE_NAME = "Dockerfile.searchservice"
FULLY_QUALIFIED_HANDLER_NAME = "taiservice.searchservice.main:create_app"
CWD = os.getcwd()


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
        target_group: ApplicationTargetGroup = self._get_target_group(services, target_port, target_protocol=ApplicationProtocol.HTTP)
        for service in services:
            self._get_scalable_task(service, target_group)
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
                resources=[
                    "*",
                ],
            ),
        )
        cluster: Cluster = self._get_cluster()
        self._get_container_definition(task_definition, container_port)
        security_group = self._get_ec2_security_group(target_port)
        service: Ec2Service = Ec2Service(
            self,
            self._namer("service"),
            service_name=self._namer("service"),
            cluster=cluster,
            desired_count=1,
            min_healthy_percent=0,
            max_healthy_percent=100,
            task_definition=task_definition,
            security_groups=[security_group, sg_for_connecting_to_db],
        )
        return service

    def _create_docker_file(self, target_port: int) -> None:
        docker_file_path = os.path.join(CWD, DOCKER_FILE_NAME)
        with open(docker_file_path, "w", encoding="utf-8") as f:
            f.write(self._search_service_settings.get_docker_file_contents(target_port, FULLY_QUALIFIED_HANDLER_NAME))

    def _get_cluster(self) -> Cluster:
        cluster = Cluster(
            self,
            self._namer("cluster"),
            vpc=self.vpc,
        )
        # gpu_asg = self._get_auto_scaling_group(ECSServiceType.GPU)
        no_gpu_asg = self._get_auto_scaling_group(ECSServiceType.NO_GPU)
        # cluster.add_asg_capacity_provider(
        #     provider=AsgCapacityProvider(
        #         self,
        #         self._namer("asg-provider-gpu"),
        #         auto_scaling_group=gpu_asg,
        #         capacity_provider_name=self._namer("capacity-provider-gpu"),
        #         enable_managed_termination_protection=False,
        #     ),
        # )
        cluster.add_asg_capacity_provider(
            provider=AsgCapacityProvider(
                self,
                self._namer("asg-provider-no-gpu"),
                auto_scaling_group=no_gpu_asg,
                capacity_provider_name=self._namer("capacity-provider-no-gpu"),
                enable_managed_termination_protection=False,
            ),
        )
        return cluster

    def _get_auto_scaling_group(self, service_type: ECSServiceType) -> AutoScalingGroup:
        ami = EcsOptimizedImage.amazon_linux2(
            hardware_type=AmiHardwareType.GPU,
        ) if service_type == ECSServiceType.GPU else EcsOptimizedImage.amazon_linux2(
            hardware_type=AmiHardwareType.STANDARD,
        )
        block_devices = [
            BlockDevice(
                device_name="/dev/xvda",
                volume=BlockDeviceVolume.ebs(
                    volume_type=EbsDeviceVolumeType.IO1,
                    delete_on_termination=True,
                    volume_size=200,
                    iops=10000, # must be 50x the volume size or less
                ),
            ),
        ]
        TIME_ZONE = "US/Mountain"
        DAY_OF_WEEK = "MON"
        GPU_START_HOUR = 6
        GPU_END_HOUR = 8
        BUFFER_FOR_SERVICE_SWITCH_MINUTES = 20
        max_num_instances = 2
        if service_type == ECSServiceType.GPU:
            instance_type = ec2.InstanceType.of(
                instance_class=ec2.InstanceClass.G4DN,
                instance_size=ec2.InstanceSize.XLARGE,
            )
            asg = AutoScalingGroup(
                self,
                self._namer("gpu-asg"),
                vpc=self.vpc,
                instance_type=instance_type,
                machine_image=ami,
                max_capacity=max_num_instances,
                min_capacity=1,
                # spot_price="0.35",
                block_devices=block_devices,
            )
            asg.scale_on_schedule(
                self._namer("gpu-scale-up"),
                schedule=Schedule.cron(hour=str(GPU_START_HOUR), minute="0", week_day=DAY_OF_WEEK),
                min_capacity=1,
                max_capacity=1,
                time_zone=TIME_ZONE,
            )
            asg.scale_on_schedule(
                self._namer("gpu-scale-down"),
                schedule=Schedule.cron(hour=str(GPU_END_HOUR), minute="0", week_day=DAY_OF_WEEK),
                min_capacity=0,
                max_capacity=0,
                time_zone=TIME_ZONE,
            )
        else:
            instance_type = ec2.InstanceType.of(
                instance_class=ec2.InstanceClass.R6A,
                instance_size=ec2.InstanceSize.LARGE,
            )
            asg = AutoScalingGroup(
                self,
                self._namer(f"asg-{service_type.value}"),
                vpc=self.vpc,
                instance_type=instance_type,
                machine_image=ami,
                max_capacity=max_num_instances,
                min_capacity=1,
                # spot_price="0.35",
                block_devices=block_devices,
                
            )
            # TODO: once we support gpu, we'll add a schedule to switch between the two during busy times
            # asg.scale_on_schedule(
            #     self._namer("scale-up"),
            #     schedule=Schedule.cron(hour=str(GPU_END_HOUR - 1), minute=str(60 - BUFFER_FOR_SERVICE_SWITCH_MINUTES), week_day=DAY_OF_WEEK),
            #     min_capacity=1,
            #     max_capacity=1,
            #     time_zone=TIME_ZONE,
            # )
            # asg.scale_on_schedule(
            #     self._namer("scale-down"),
            #     schedule=Schedule.cron(hour=str(GPU_START_HOUR), minute=str(BUFFER_FOR_SERVICE_SWITCH_MINUTES), week_day=DAY_OF_WEEK),
            #     min_capacity=0,
            #     max_capacity=0,
            #     time_zone=TIME_ZONE,
            # )
            # create a schedule that schedules the service to run between 6am and midnight
            asg.scale_on_schedule(
                self._namer("scale-up"),
                schedule=Schedule.cron(hour="6", minute="0", week_day="*"),
                min_capacity=1,
                max_capacity=1,
                time_zone=TIME_ZONE,
            )
            asg.scale_on_schedule(
                self._namer("scale-down"),
                schedule=Schedule.cron(hour="23", minute="0", week_day="*"),
                min_capacity=0,
                max_capacity=0,
                time_zone=TIME_ZONE,
            )
        asg.scale_on_cpu_utilization(
            id=self._namer("asg-cpu-scaling"),
            target_utilization_percent=50,
            # this needs to be pretty long as it takes a bit for the container to place
            # due to the large container image size
            cooldown=Duration.seconds(600),
            disable_scale_in=False,
        )
        return asg

    def _get_container_definition(self, task_definition: Ec2TaskDefinition, container_port: int) -> ContainerDefinition:
        container: ContainerDefinition = task_definition.add_container(
            self._namer("container"),
            image=ContainerImage.from_asset(directory=CWD, file=DOCKER_FILE_NAME),
            environment=self._search_service_settings.dict(for_environment=True, export_aws_vars=True),
            logging=LogDriver.aws_logs(stream_prefix=self._namer("log")),
            gpu_count=0,
            memory_limit_mib=15000,
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

    def _get_scalable_task(self, service: Ec2Service, target_group: ApplicationTargetGroup) -> ScalableTaskCount:
        scaling_task = service.auto_scale_task_count(
            max_capacity=4,
            min_capacity=1,
        )
        scaling_task.scale_on_cpu_utilization(
            id=self._namer("task-cpu-scaling"),
            target_utilization_percent=50,
            # this needs to be pretty long as it takes a bit for the container to place
            # due to the large container image size
            scale_out_cooldown=Duration.seconds(600),
            disable_scale_in=False,
        )
        return scaling_task

    def _get_target_group(self, services: list[Ec2Service], target_port: int, target_protocol: ApplicationProtocol) -> ApplicationTargetGroup:
        alb: ApplicationLoadBalancer = ApplicationLoadBalancer(
            self,
            self._namer("alb"),
            vpc=self.vpc,
            internet_facing=True
        )
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
        )
        return target_group
