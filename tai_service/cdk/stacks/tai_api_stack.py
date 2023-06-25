"""Define the stack for the TAI API service."""
from typing import Union
from constructs import Construct
from pydantic import Field
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_ec2 as ec2,
)
from ..stack_config_models import StackConfigBaseModel
from ..constructs.python_lambda_construct import PythonLambda, PythonLambdaConfigModel
from ..constructs.construct_helpers import (
    get_secret_arn_from_name,
    create_restricted_security_group,
    get_vpc,
)






class TaiApiStack(Stack):
    """Define the stack for the TAI API service."""

    def __init__(
        self,
        scope: Construct,
        config: StackConfigBaseModel,
        api_settings: TaiApiSettings,
        vpc: Union[ec2.IVpc, ec2.Vpc, str],
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
        self._settings = api_settings

    def _create_custom_resource(self) -> _lambda.Function:
        config = self._get_lambda_config()
        name = config.function_name
        lambda_function = PythonLambda.get_lambda_function(
            self,
            construct_id=f"{name}-lambda",
        )
        self._add_secrets_to_lambda_role(lambda_function)
        return lambda_function

    def _add_secrets_to_lambda_role(self, lambda_function: _lambda.Function) -> None:
        """Add the secrets to the lambda role."""
        lambda_function.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                effect=iam.Effect.ALLOW,
                resources=[get_secret_arn_from_name(self, self._settings.password_secret_name)],
            )
        )

    def _get_lambda_config(self) -> PythonLambdaConfigModel:
        security_group = create_restricted_security_group(
            name="lambda",
            description="The security group for the DocumentDB lambda.",
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
