"""Define the Pinecone database construct."""
from pathlib import Path
from constructs import Construct
import hashlib
from aws_cdk import (
    aws_iam as iam,
    custom_resources as cr,
    CustomResource,
    Duration,
    Size as StorageSize,
)
from .customresources.pinecone_db.pinecone_db_setup_lambda import PineconeDBSettings
from .python_lambda_props_builder import (
    PythonLambdaPropsBuilderConfigModel,
    PythonLambdaPropsBuilder,
)

PINECONE_CUSTOM_RESOURCE_DIR = Path(__file__).parent / "customresources" / "pinecone_db"
CDK_DIR = Path(__file__).parent.parent.parent
SRC_DIR = CDK_DIR.parent

class PineconeDatabase(Construct):
    """Define the Pinecone database construct."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        pinecone_db_api_secret_arn: str,
        db_settings: PineconeDBSettings,
        **kwargs,
    ) -> None:
        """Initialize the Pinecone database construct."""
        super().__init__(scope, construct_id, **kwargs)
        self._secret_arn = pinecone_db_api_secret_arn
        self._db_settings = db_settings
        self.custom_resource_provider = self._create_custom_resource()

    def _create_custom_resource(self) -> cr.Provider:
        config = self._get_lambda_config()
        name = config.function_name
        lambda_function = PythonLambdaPropsBuilder.get_lambda_function(
            self,
            construct_id=f"custom-resource-lambda-{name}",
            config=config,
        )
        lambda_function.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                effect=iam.Effect.ALLOW,
                resources=[self._secret_arn],
            )
        )
        provider = cr.Provider(
            self,
            id="custom-resource-provider",
            on_event_handler=lambda_function,
            provider_function_name=name + "-PROVIDER",
        )
        custom_resource = CustomResource(
            self,
            id="custom-resource",
            service_token=provider.service_token,
            properties={"hash": self._get_hash_for_all_files_in_dir(SRC_DIR)},
        )
        return custom_resource


    def _get_hash_for_all_files_in_dir(self, dir_path: Path) -> str:
        """Return a hash of all files in a directory."""
        hash_string = ""
        for file_path in dir_path.glob("**/*"):
            if file_path.is_file():
                with open(file_path, "rb") as file:
                    bytes_buffer = file.read()
                    hash_string += hashlib.md5(bytes_buffer).hexdigest()
        hash_string = hashlib.md5(hash_string.encode("utf-8")).hexdigest()
        return hash_string

    def _get_lambda_config(self) -> PythonLambdaPropsBuilderConfigModel:
        lambda_config = PythonLambdaPropsBuilderConfigModel(
            function_name="pinecone-db-custom-resource",
            description="Custom resource for performing CRUD operations on the pinecone database",
            code_path=PINECONE_CUSTOM_RESOURCE_DIR,
            handler_module_name="main",
            handler_name="lambda_handler",
            runtime_environment=self._db_settings,
            requirements_file_path=PINECONE_CUSTOM_RESOURCE_DIR / "requirements.txt",
            files_to_copy_into_handler_dir=[
                CDK_DIR / "schemas.py",
                PINECONE_CUSTOM_RESOURCE_DIR.parent / "custom_resource_interface.py",
            ],
            timeout=Duration.minutes(3),
            memory_size=128,
            ephemeral_storage_size=StorageSize.mebibytes(512),
        )
        return lambda_config
