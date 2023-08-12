"""Define the search database stack."""
import os
from typing import Optional, Any
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
)
from aws_cdk.aws_ecs import (
    Cluster,
    Ec2TaskDefinition,
    Ec2Service,
    PortMapping,
    ContainerImage,
    ContainerDefinition,
    AddCapacityOptions,
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
)
from tai_aws_account_bootstrap.stack_helpers import add_tags
from tai_aws_account_bootstrap.stack_config_models import StackConfigBaseModel
from taiservice.searchservice.runtime_settings import SearchServiceSettings
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

class TaiSearchServiceStack(Stack):
    """Define the search service for indexing and searching."""

    def __init__(
        self,
        scope: Construct,
        config: StackConfigBaseModel,
        pinecone_db_settings: PineconeDBSettings,
        doc_db_settings: DocumentDBSettings,
        search_service_settings: SearchServiceSettings,
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
        self.search_service = self._get_search_service(self._security_group_for_connecting_to_doc_db)
        self._cold_store_bucket: VersionedBucket = VersionedBucket.create_bucket(
            scope=self,
            bucket_name=search_service_settings.cold_store_bucket_name,
            public_read_access=True,
            permissions=Permissions.READ_WRITE,
            removal_policy=config.removal_policy,
            role=self.search_service.task_definition.task_role,
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

    def _get_search_service(self, sg_for_connecting_to_db: ec2.SecurityGroup) -> Ec2Service:
        target_port = 80
        container_port = 8080
        self._create_docker_file(container_port)
        cluster: Cluster = self._get_cluster()
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
        self._get_container_definition(task_definition, container_port)
        security_group = self._get_ec2_security_group(target_port)
        service: Ec2Service = Ec2Service(
            self,
            self._namer("service"),
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            security_groups=[security_group, sg_for_connecting_to_db],
        )
        target_group: ApplicationTargetGroup = self._get_target_group(service, target_port, target_protocol=ApplicationProtocol.HTTP)
        self._get_scalable_task(service, target_group)
        return service

    def _create_docker_file(self, target_port: int) -> None:
        docker_file_path = os.path.join(CWD, DOCKER_FILE_NAME)
        with open(docker_file_path, "w", encoding="utf-8") as f:
            f.write(self._search_service_settings.get_docker_file_contents(target_port, FULLY_QUALIFIED_HANDLER_NAME))

    def _get_cluster(self) -> Cluster:
        deep_learning_ami = EcsOptimizedImage.amazon_linux2(
            hardware_type=AmiHardwareType.GPU,
        )
        instance_type = ec2.InstanceType.of(
            # using this in the stack is expensive. we want to be able to manually change 
            # the instance type to gpu when needed in the console when needed to save on costs
            # instance_class=ec2.InstanceClass.G4DN,
            instance_class=ec2.InstanceClass.R6A,
            instance_size=ec2.InstanceSize.LARGE,
            # instance_size=ec2.InstanceSize.XLARGE, # smae here, this is for GPU
        )
        cluster = Cluster(
            self,
            self._namer("cluster"),
            vpc=self.vpc,
        )
        auto_scaling_group = AutoScalingGroup(
            self,
            self._namer("asg"),
            vpc=self.vpc,
            instance_type=instance_type,
            machine_image=deep_learning_ami,
            instance_type=instance_type,
            max_capacity=2,
            min_capacity=1,
            machine_image=deep_learning_ami,
            # spot_price="0.35",
            block_devices=[
                BlockDevice(
                    device_name="/dev/xvda",
                    volume=BlockDeviceVolume.ebs(
                        volume_type=EbsDeviceVolumeType.IO1,
                        delete_on_termination=True,
                        volume_size=200,
                        iops=10000, # must be 50x the volume size or less
                    ),
                ),
            ],
        )
        cluster.add_asg_capacity_provider(
            provider=AsgCapacityProvider(
                self,
                self._namer("asg-provider"),
                auto_scaling_group=auto_scaling_group,
                capacity_provider_name=self._namer("asg-provider"),
            ),
        )
        return cluster
    
    def _get_container_definition(self, task_definition: Ec2TaskDefinition, container_port: int) -> ContainerDefinition:
        container: ContainerDefinition = task_definition.add_container(
            self._namer("container"),
            image=ContainerImage.from_asset(directory=CWD, file=DOCKER_FILE_NAME),
            memory_limit_mib=4000,
            environment=self._search_service_settings.dict(),
            logging=LogDriver.aws_logs(stream_prefix=self._namer("log")),
            gpu_count=0, # setting this to 0 so we can update the container as updates require 2 gpus during the overlap period.
            cpu=1000, # 1024 = 1 vCPU
        )
        container.add_port_mappings(
            PortMapping(container_port=container_port),
        )
        return container

    def _get_ec2_security_group(self, target_port: int) -> ec2.SecurityGroup:
        target_sg: ec2.SecurityGroup = ec2.SecurityGroup(
            self,
            self._namer("sg"),
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
            max_capacity=2,
            min_capacity=1,
        )
        scaling_task.scale_on_cpu_utilization(
            self._namer("cpu-scaling"),
            target_utilization_percent=80,
        )
        scaling_task.scale_on_request_count(
            self._namer("request-scaling"),
            target_group=target_group,
            requests_per_target=100,
        )
        return scaling_task

    def _get_target_group(self, service: Ec2Service, target_port: int, target_protocol: ApplicationProtocol) -> ApplicationTargetGroup:
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
            targets=[service],
        )
        return target_group
