"""Define the Pinecone database construct."""
from pathlib import Path
from constructs import Construct
from aws_cdk import (
    aws_iam as iam,
    custom_resources as cr,
    CustomResource,
    Duration,
    Size as StorageSize,
)
from .customresources.pinecone_db.pinecone_db_custom_resource import PineconeDBSettings
from .construct_helpers import get_hash_for_all_files_in_dir, get_secret_arn_from_name
from .python_lambda_construct import (
    PythonLambdaConfigModel,
    PythonLambda,
)

CONSTRUCTS_DIR = Path(__file__).parent
PINECONE_CUSTOM_RESOURCE_DIR = CONSTRUCTS_DIR / "customresources" / "pinecone_db"

class PineconeDatabase(Construct):
    """Define the Pinecone database construct."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        db_settings: PineconeDBSettings,
        **kwargs,
    ) -> None:
        """Initialize the Pinecone database construct."""
        super().__init__(scope, construct_id, **kwargs)
        self._secret_arn = get_secret_arn_from_name(db_settings.api_key_secret_name)
        self._db_settings = db_settings
        self.custom_resource_provider = self._create_custom_resource()

    def _create_custom_resource(self) -> cr.Provider:
        config = self._get_lambda_config()
        name = config.function_name
        python_lambda = PythonLambda.get_lambda_function(
            self,
            construct_id=f"custom-resource-lambda-{name}",
            config=config,
        )
        python_lambda.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                effect=iam.Effect.ALLOW,
                resources=[self._secret_arn],
            )
        )
        provider: cr.Provider = cr.Provider(
            self,
            id="custom-resource-provider",
            on_event_handler=python_lambda.lambda_function,
            provider_function_name=name + "-PROVIDER",
        )
        custom_resource = CustomResource(
            self,
            id="custom-resource",
            service_token=provider.service_token,
            properties={"hash": get_hash_for_all_files_in_dir(CONSTRUCTS_DIR)},
        )
        return custom_resource

    def _get_lambda_config(self) -> PythonLambdaConfigModel:
        lambda_config = PythonLambdaConfigModel(
            function_name="pinecone-db-custom-resource",
            description="Custom resource for performing CRUD operations on the pinecone database",
            code_path=PINECONE_CUSTOM_RESOURCE_DIR,
            handler_module_name="main",
            handler_name="lambda_handler",
            runtime_environment=self._db_settings,
            requirements_file_path=PINECONE_CUSTOM_RESOURCE_DIR / "requirements.txt",
            files_to_copy_into_handler_dir=[
                CONSTRUCTS_DIR / "construct_config.py",
                PINECONE_CUSTOM_RESOURCE_DIR.parent / "custom_resource_interface.py",
            ],
            timeout=Duration.minutes(3),
            memory_size=128,
            ephemeral_storage_size=StorageSize.mebibytes(512),
        )
        return lambda_config
