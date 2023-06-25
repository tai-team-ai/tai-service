"""Define the search service app."""
from aws_cdk import App
from tai_service.cdk.stacks.search_database_stack import SearchServiceDatabases
from tai_service.cdk.stacks.tai_api_stack import TaiApiStack
from tai_service.cdk.stacks.search_databases_settings import (
    DOCUMENT_DB_SETTINGS,
    PINECONE_DB_SETTINGS,
)
from tai_service.cdk.stacks.tai_api_settings import TAI_API_SETTINGS
from tai_service.cdk.stack_config_models import (
    StackConfigBaseModel,
    AWSDeploymentSettings,
)

app: App = App()

AWS_DEPLOYMENT_SETTINGS = AWSDeploymentSettings()

base_stack_config = StackConfigBaseModel(
	stack_id="default-stack",
	stack_name="default-stack",
	description="Default stack for the tai service. This stack contains the search service " \
    deployment_settings=AWS_DEPLOYMENT_SETTINGS,
    duplicate_stack_for_development=True,
    termination_protection=False,
    tags={
        'blame': 'jacob',
    }
)

search_databases_config = StackConfigBaseModel(
	stack_id="search-service-databases",
	stack_name="search-service-databases",
	description="Stack for the search service databases. This stack contains the document " \
    	"database and the pinecone database used by the tai search service.",
    **base_stack_config.dict(),
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
    **base_stack_config.dict(),
)
tai_api = TaiApiStack(
    scope=app,
    config=tai_api_config,
    api_settings=TAI_API_SETTINGS,
    vpc=search_service_databases.vpc,
)

app.synth()
