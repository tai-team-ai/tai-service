"""Define the runtime settings for the TAI Search Service."""
import json
from typing import Any, Union, Optional
from enum import Enum
from pathlib import Path
from pydantic import Field, BaseSettings
import boto3
from botocore.exceptions import ClientError
from .backend.databases.pinecone_db import Environment as PineconeEnvironment


BACKEND_ATTRIBUTE_NAME = "tai_backend"


class AWSRegion(str, Enum):
    """Define valid AWS regions."""

    US_EAST_1 = "us-east-1"
    US_EAST_2 = "us-east-2"
    US_WEST_1 = "us-west-1"
    US_WEST_2 = "us-west-2"


class LogLevel(str, Enum):
    """Define valid log levels."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Secret(BaseSettings):
    """Define the secret model."""
    secret_name: str = Field(
        ...,
        description="The name of the secret.",
    )

    @property
    def secret_value(self) -> Union[dict[str, Any], str]:
        """Return the secret value."""
        return self.get_secret_value(self.secret_name)

    @staticmethod
    def get_secret_value(secret_name: str) -> Union[dict[str, Any], str]:
        """Get the secret value."""
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager")
        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        except ClientError as e:
            raise RuntimeError(f"Failed to get secret value: {e}") from e
        secret = get_secret_value_response["SecretString"]
        try:
            return json.loads(secret)
        except json.JSONDecodeError:
            return secret


class Secrets(BaseSettings):
    """Define the secrets model."""
    secrets: list[Secret] = Field(
        ...,
        description="The list of secrets.",
    )

    def get_kwargs(self) -> dict[str, Any]:
        """Return the kwargs."""
        kwargs = {}
        for secret in self.secrets:
            kwargs[secret.secret_name] = secret.secret_value
        return kwargs


class SearchServiceSettings(BaseSettings):
    """Define the configuration model for the TAI API service."""

    aws_default_region: AWSRegion = Field(
        default=AWSRegion.US_EAST_1,
        description="The default AWS region to use with the service.",
    )
    pinecone_db_api_key_secret_name: str = Field(
        ...,
        description="The name of the secret containing the Pinecone API key.",
    )
    pinecone_db_environment: PineconeEnvironment = Field(
        ...,
        description="The environment of the pinecone db.",
    )
    pinecone_db_index_name: str = Field(
        ...,
        description="The name of the pinecone index.",
    )
    doc_db_credentials_secret_name: str = Field(
        ...,
        description="The name of the secret containing the document database credentials.",
    )
    doc_db_username_secret_key: str = Field(
        default="username",
        const=True,
        description="The name of the secret key containing the document database username.",
    )
    doc_db_password_secret_key: str = Field(
        default="password",
        const=True,
        description="The name of the secret key containing the document database password.",
    )
    doc_db_fully_qualified_domain_name: str = Field(
        ...,
        description="The fully qualified domain name of the TAI API service.",
    )
    doc_db_port: int = Field(
        default=27017,
        description="The port of the TAI API service.",
    )
    doc_db_database_name: str = Field(
        ...,
        description="The name of the document db.",
    )
    doc_db_class_resource_collection_name: str = Field(
        ...,
        description="The name of the collection in the document db for class resources.",
    )
    doc_db_class_resource_chunk_collection_name: str = Field(
        ...,
        description="The name of the collection in the document db for class resource chunks.",
    )
    openAI_api_key_secret_name: str = Field(
        ...,
        description="The name of the secret containing the OpenAI API key.",
    )
    openAI_request_timeout: int = Field(
        default=30,
        description="The timeout for OpenAI requests.",
    )
    openAI_batch_size: int = Field(
        default=50,
        description="The batch size for OpenAI requests.",
    )
    nltk_data: Path = Field(
        default=Path("/tmp/nltk_data"),
        description="The path to the nltk data.",
    )
    transformers_cache: Path = Field(
        default=Path("/tmp/transformers_cache"),
        description="The path to the transformers cache.",
    )
    cold_store_bucket_name: str = Field(
        default="tai-service-class-resource-cold-store",
        description="The name of the cold store bucket.",
    )
    documents_to_index_queue: str = Field(
        default="tai-service-documents-to-index-queue",
        description="The name of the data to index transfer bucket. Documents should be uploaded to this bucket.",
    )
    chrome_driver_path: Path = Field(
        default=Path("/var/task/chromedriver"),
        description="The path to the chrome driver.",
    )
    class_resource_processing_timeout: int = Field(
        default=900,
        ge=300,
        le=1000,
        description="The timeout for class resource processing.",
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="The log level for the service.",
    )
    mathpix_api_secret: Optional[Secret] = Field(
        default=None,
        description="The secrets for the Mathpix API.",
    )

    class Config:
        """Define the Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def secret_names(self) -> list[str]:
        """Return the names of the secrets used by the service."""
        secrets = [
            self.openAI_api_key_secret_name,
            self.doc_db_credentials_secret_name,
            self.pinecone_db_api_key_secret_name,
            self.mathpix_api_secret.secret_name if self.mathpix_api_secret else None,
        ]
        output = []
        for secret in secrets:
            if secret:
                output.append(secret)
        return output

    def get_docker_file_contents(
        self,
        port: int,
        fully_qualified_handler_path: str,
        worker_count: int = 1,
    ) -> str:
        """Create and return the path to the Dockerfile."""
        docker_file = [
            # "FROM python:3.10 as dependencies",
            "FROM 763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.0.1-gpu-py310-cu118-ubuntu20.04-ec2 AS build",
            "RUN rm /etc/apt/sources.list.d/cuda.list && apt-get update && apt-get install -y curl",
            "RUN curl -sL https://deb.nodesource.com/setup_18.x | bash",
            # poppler-utils is used for the python pdf to image package
            "RUN apt-get update && \\\
                \n\tapt-get install -y nodejs poppler-utils wget unzip\\\
                \n\tlibglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 chromium-browser",  # chrome deps
            # install chrome driver for selenium use
            # install extra dependencies for chrome driver
            f"RUN mkdir -p {self.chrome_driver_path}",
            f"RUN wget -O {self.chrome_driver_path}.zip https://chromedriver.storage.googleapis.com/90.0.4430.24/chromedriver_linux64.zip",
            # unzip to the self._settings.chrome_driver_path directory
            f"RUN unzip {self.chrome_driver_path}.zip -d {self.chrome_driver_path}",
            "\nFROM build AS dependencies",
            "WORKDIR /app",
            "RUN pip install --upgrade pip && pip install nltk projen uvicorn",
            f"RUN mkdir -p {self.nltk_data}",  # Create directory for model
            # punkt and and stopwords are used for pinecone SPLADE
            # averaged_perceptron_tagger is used for langchain for HTML parsing
            # the path is specified as lambda does NOT have access to the default path
            f"RUN python3 -m nltk.downloader -d {self.nltk_data} punkt stopwords averaged_perceptron_tagger",  # Download the model and save it to the directory
            "COPY requirements.txt .",
            "RUN pip install -r requirements.txt",
            "\nFROM dependencies AS runtime",
            "WORKDIR /app",
            "COPY . .",
            f"EXPOSE {port}",
            "# The --max-request is to restart workers to help clear the memory used by pytorch",
            f'CMD ["gunicorn", "-w", "{worker_count}", "-k", "uvicorn.workers.UvicornWorker", '
            f'"{fully_qualified_handler_path}", "--bind", "0.0.0.0:{port}", "--worker-tmp-dir", "/dev/shm", '
            '"--graceful-timeout", "900", "--timeout", "1800", "--max-requests", "10"]',
            # f'CMD [".venv/bin/python", "-m", "uvicorn", "{fully_qualified_handler_path}", "--host", "0.0.0.0", "--port", "{port}", "--factory"]',
        ]
        return "\n".join(docker_file)
