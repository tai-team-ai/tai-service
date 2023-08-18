"""Define the runtime settings for the TAI Search Service."""
from enum import Enum
from pathlib import Path
from pydantic import Field, BaseSettings
from .backend.databases.pinecone_db import Environment as PineconeEnvironment


BACKEND_ATTRIBUTE_NAME = "tai_backend"


class AWSRegion(str, Enum):
    """Define valid AWS regions."""
    US_EAST_1 = "us-east-1"
    US_EAST_2 = "us-east-2"
    US_WEST_1 = "us-west-1"
    US_WEST_2 = "us-west-2"


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
        default=Path("/var/task/nltk_data"),
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
        default=240,
        description="The timeout for class resource processing.",
    )

    class Config:
        """Define the Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_docker_file_contents(self, port: int, fully_qualified_handler_path: str) -> str:
        """Create and return the path to the Dockerfile."""
        docker_file = [
            # "FROM python:3.10 as dependencies",
            "FROM 763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.0.1-gpu-py310-cu118-ubuntu20.04-ec2 AS build",
            "RUN rm /etc/apt/sources.list.d/cuda.list && apt-get update && apt-get install -y curl",
            "RUN curl -sL https://deb.nodesource.com/setup_18.x | bash",
            # poppler-utils is used for the python pdf to image package
            "RUN apt-get update && \\\
                \n\tapt-get install -y nodejs poppler-utils wget unzip",
            # install chrome driver for selenium use
            # install extra dependencies for chrome driver
            f"RUN mkdir -p {self.chrome_driver_path}",
            f"RUN wget -O {self.chrome_driver_path}.zip https://chromedriver.storage.googleapis.com/90.0.4430.24/chromedriver_linux64.zip",
            # unzip to the self._settings.chrome_driver_path directory
            f"RUN unzip {self.chrome_driver_path}.zip -d {self.chrome_driver_path}",
            "RUN apt-get install -y libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 chromium-browser",
            "\nFROM build AS dependencies",
            "WORKDIR /app",
            "RUN pip install --upgrade pip && pip install nltk projen uvicorn",
            f"RUN mkdir -p {self.nltk_data}",  # Create directory for model
            # punkt and and stopwords are used for pinecone SPLADE
            # averaged_perceptron_tagger is used for langchain for HTML parsing
            # the path is specified as lambda does NOT have access to the default path
            f"RUN python3 -m nltk.downloader -d {self.nltk_data} punkt stopwords averaged_perceptron_tagger",  # Download the model and save it to the directory
            "COPY .projenrc.py .projenrc.py",
            "COPY .projen .projen",
            "RUN projen",
            "\nFROM dependencies AS runtime",
            "WORKDIR /app",
            "COPY . .",
            f"EXPOSE {port}",
            f'CMD [".venv/bin/python", "-m", "uvicorn", "{fully_qualified_handler_path}", "--host", "0.0.0.0", "--port", "{port}", "--factory"]',
        ]
        return "\n".join(docker_file)
