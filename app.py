"""Define the search service app."""
from aws_cdk import App
from tai_service.cdk.stacks.search_database_stack import SearchServiceDatabases
from tai_service.schemas import (
    AdminDocumentDBSettings,
    BasePineconeDBSettings,
)
from tai_service.cdk.stack_config_models import (
    StackConfigBaseModel,
    AWSDeploymentSettings,
)

app = App()

AWS_DEPLOYMENT_SETTINGS = AWSDeploymentSettings()

base_stack_config = StackConfigBaseModel(
	stack_id="search-service-databases",
	stack_name="search-service-databases",
	description="Stack for the search service databases. This stack contains the document " \
    	"database and the pinecone database used by the tai search service.",
    deployment_settings=AWS_DEPLOYMENT_SETTINGS,
    duplicate_stack_for_development=True,
    termination_protection=False,
    tags={
        'blame': 'jacob',
    }
)

doc_db_settings = AdminDocumentDBSettings()
pinecone_db_settings = BasePineconeDBSettings()

search_service_databases = SearchServiceDatabases(
    app,
	config=base_stack_config,
	doc_db_settings=doc_db_settings,
	pinecone_db_settings=pinecone_db_settings,
)


app.synth()
