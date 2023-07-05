"""Define the search service app."""
import os
from aws_cdk import App
from dotenv import load_dotenv
from taiservice.cdk.stacks.search_database_stack import SearchServiceDatabases
from taiservice.cdk.stacks.tai_api_stack import TaiApiStack
from taiservice.cdk.stacks.search_databases_settings import (
    DOCUMENT_DB_SETTINGS,
    PINECONE_DB_SETTINGS,
)
from taiservice.cdk.stacks.tai_api_settings import TAI_API_SETTINGS
from taiservice.cdk.stacks.stack_config_models import (
    StackConfigBaseModel,
    AWSDeploymentSettings,
)

app: App = App()
load_dotenv()

AWS_DEPLOYMENT_SETTINGS = AWSDeploymentSettings()
TAGS = {'blame': 'jacob'}

search_databases_config = StackConfigBaseModel(
	stack_id="tai-search-service-databases",
	stack_name="tai-search-service-databases",
	description="Stack for the search service databases. This stack contains the document " \
    	"database and the pinecone database used by the tai search service.",
    deployment_settings=AWS_DEPLOYMENT_SETTINGS,
    duplicate_stack_for_development=False,
    termination_protection=False,
    tags=TAGS,
)
search_service_databases: SearchServiceDatabases = SearchServiceDatabases(
    scope=app,
	config=search_databases_config,
    doc_db_settings=DOCUMENT_DB_SETTINGS,
    pinecone_db_settings=PINECONE_DB_SETTINGS,
)

tai_api_config = StackConfigBaseModel(
    stack_id="tai-api",
    stack_name="tai-api",
    description="Stack for the tai api service. This stack contains the tai api service.",
    deployment_settings=AWS_DEPLOYMENT_SETTINGS,
    duplicate_stack_for_development=True,
    termination_protection=False,
    tags=TAGS,
)
TAI_API_SETTINGS.doc_db_fully_qualified_domain_name = search_service_databases.document_db.fully_qualified_domain_name
tai_api = TaiApiStack(
    scope=app,
    config=tai_api_config,
    api_settings=TAI_API_SETTINGS,
    vpc=search_service_databases.vpc,
    security_group_allowing_db_connections=search_service_databases.security_group_for_connecting_to_doc_db,
)

app.synth()
