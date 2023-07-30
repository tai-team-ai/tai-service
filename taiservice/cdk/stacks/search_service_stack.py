"""Define the stack to deploy the search service."""
from typing import Union
from constructs import Construct
from aws_cdk import Stack
from aws_cdk.aws_ecs import (
    Cluster,
    Ec2TaskDefinition,
    Ec2Service,
    PortMapping,
    ContainerImage,
    ContainerDefinition,
    AddCapacityOptions,
    ScalableTaskCount,
)
from aws_cdk.aws_elasticloadbalancingv2 import (
    ApplicationLoadBalancer,
    ApplicationProtocol,
    ApplicationTargetGroup,
)
from aws_cdk.aws_ec2 import (
    IVpc,
    Vpc,
    InstanceType,
    InstanceClass,
    InstanceSize,
    SecurityGroup,
    Port,
    Peer,
)
from .stack_config_models import StackConfigBaseModel
from ..constructs.construct_helpers import get_vpc


PATH_TO_SERVICE_DIR = "taiservice/searchservice"


class TaiSearchServiceStack(Stack):

    def __init__(
        self,
        scope: Construct,
        config: StackConfigBaseModel,
        vpc: Union[IVpc, Vpc, str],
        sg_for_connecting_to_db: SecurityGroup,
        **kwargs
    ) -> None:
        super().__init__(
            scope=scope,
            id=config.stack_id,
            stack_name=config.stack_name,
            description=config.description,
            env=config.deployment_settings.aws_environment,
            tags=config.tags,
            termination_protection=config.termination_protection,
        )
        self._namer = config.namer
        self._vpc = get_vpc(vpc)
        target_port = 80
        cluster: Cluster = self._get_cluster()
        task_definition: Ec2TaskDefinition = Ec2TaskDefinition(
            self,
            self._namer("task"),
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

    def _get_cluster(self) -> Cluster:
        instance_type = InstanceType.of(
            instance_class=InstanceClass.BURSTABLE3,
            instance_size=InstanceSize.SMALL,
        )
        cluster = Cluster(
            self,
            self._namer("cluster"),
            vpc=self._vpc,
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
            PortMapping(container_port=8080, host_port=80)
        )
        return container

    def _get_ec2_security_group(self, target_port: int) -> SecurityGroup:
        target_sg: SecurityGroup = SecurityGroup(
            self,
            self._namer("sg"),
            vpc=self._vpc,
            allow_all_outbound=True,
        )
        target_sg.add_ingress_rule(
            peer=Peer.any_ipv4(),
            connection=Port.tcp(target_port),
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
            vpc=self._vpc,
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
