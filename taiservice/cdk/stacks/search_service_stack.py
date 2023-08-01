"""Define the search database stack."""
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
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
)
from aws_cdk.aws_elasticloadbalancingv2 import (
    ApplicationLoadBalancer,
    ApplicationProtocol,
    ApplicationTargetGroup,
)
from .stack_helpers import add_tags
from .stack_config_models import StackConfigBaseModel
from ..constructs.document_db_construct import (
    DocumentDatabase,
    ElasticDocumentDBConfigModel,
    DocumentDBSettings,
)
from ..constructs.pinecone_db_construct import PineconeDatabase
from ..constructs.customresources.pinecone_db.pinecone_db_custom_resource import PineconeDBSettings



PATH_TO_SERVICE_DIR = "taiservice/searchservice"

class SearchServiceDatabases(Stack):
    """Define the search database stack."""

    def __init__(
        self,
        scope: Construct,
        config: StackConfigBaseModel,
        pinecone_db_settings: PineconeDBSettings,
        doc_db_settings: DocumentDBSettings,
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
        self._pinecone_db_settings = pinecone_db_settings
        self._doc_db_settings = doc_db_settings
        self._config = config
        self._namer = lambda name: f"{config.stack_name}-{name}"
        self._subnet_type_for_doc_db = ec2.SubnetType.PRIVATE_WITH_EGRESS
        self.vpc = self._create_vpc()
        self.document_db = self._get_document_db(doc_db_settings=doc_db_settings)
        self._security_group_for_connecting_to_doc_db = self.document_db.security_group_for_connecting_to_cluster
        self.pinecone_db = self._get_pinecone_db()
        self.search_service = self._get_search_service(self._security_group_for_connecting_to_doc_db)
        add_tags(self, config.tags)

    @property
    def security_group_for_connecting_to_doc_db(self) -> ec2.SecurityGroup:
        """
        Return the security group for connecting to the document db.

        If you want to connect to the document db from another stack, you need to use this security group.
        """
        return self._security_group_for_connecting_to_doc_db

    def _create_vpc(self) -> ec2.Vpc:
        subnet_configurations = []
        subnet_configurations.append(
            ec2.SubnetConfiguration(
                name=self._namer("subnet-isolated"),
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            )
        )
        subnet_configurations.append(
            ec2.SubnetConfiguration(
                name=self._namer("subnet-public"),
                subnet_type=ec2.SubnetType.PUBLIC,
            )
        )
        vpc = ec2.Vpc(
            scope=self,
            id=self._namer("vpc"),
            vpc_name=self._namer("vpc"),
            max_azs=3,
            nat_gateways=1,
            subnet_configuration=subnet_configurations,
        )
        subnets = ec2.SubnetSelection(one_per_az=True)
        ec2.InterfaceVpcEndpoint(
            scope=self,
            id="secrets-manager-endpoint",
            vpc=vpc,
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            subnets=subnets,
        )
        return vpc

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
        )
        return db

    def _get_search_service(self, sg_for_connecting_to_db: ec2.SecurityGroup) -> Ec2Service:
        target_port = 80
        cluster: Cluster = self._get_cluster()
        task_definition: Ec2TaskDefinition = Ec2TaskDefinition(
            self,
            self._namer("task"),
            network_mode=NetworkMode.AWS_VPC,
        )
        self._get_container_definition(task_definition)
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

    def _get_cluster(self) -> Cluster:
        instance_type = ec2.InstanceType.of(
            instance_class=ec2.InstanceClass.BURSTABLE3,
            instance_size=ec2.InstanceSize.SMALL,
        )
        cluster = Cluster(
            self,
            self._namer("cluster"),
            vpc=self.vpc,
            capacity=AddCapacityOptions(
                instance_type=instance_type,
                max_capacity=1,
            ),
        )
        return cluster

    def _get_container_definition(self, task_definition: Ec2TaskDefinition) -> ContainerDefinition:
        container: ContainerDefinition = task_definition.add_container(
            self._namer("container"),
            image=ContainerImage.from_asset(PATH_TO_SERVICE_DIR),
            memory_limit_mib=512,
        )
        container.add_port_mappings(
            PortMapping(container_port=8080)
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
            max_capacity=1
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
