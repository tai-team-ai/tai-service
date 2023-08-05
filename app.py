"""Define the search service app."""
from aws_cdk import App, RemovalPolicy
from dotenv import load_dotenv
from taiservice.cdk.stacks.search_service_stack import TaiSearchServiceStack
from taiservice.cdk.stacks.tai_api_stack import TaiApiStack
from taiservice.cdk.stacks.search_service_settings import (
    DOCUMENT_DB_SETTINGS,
    PINECONE_DB_SETTINGS,
    SEARCH_SERVICE_SETTINGS,
)
from taiservice.cdk.stacks.tai_api_settings import TAI_API_SETTINGS
from taiservice.cdk.stacks.stack_config_models import (
    StackConfigBaseModel,
    AWSDeploymentSettings,
    DeploymentType,
)
from taiservice.cdk.stacks.frontend_stack import TaiFrontendServerStack

app: App = App()
load_dotenv()

AWS_DEPLOYMENT_SETTINGS = AWSDeploymentSettings()
is_prod_deployment = AWS_DEPLOYMENT_SETTINGS.deployment_type == DeploymentType.PROD
TERMINATION_PROTECTION = True if is_prod_deployment else False
REMOVAL_POLICY = RemovalPolicy.RETAIN if is_prod_deployment else RemovalPolicy.DESTROY
TAGS = {'blame': 'jacob'}
BASE_SETTINGS = {
    "deployment_settings": AWS_DEPLOYMENT_SETTINGS,
    "termination_protection": TERMINATION_PROTECTION,
    "removal_policy": REMOVAL_POLICY,
    "tags": TAGS,
}
search_service_config = StackConfigBaseModel(
	stack_id="tai-search-service-databases",
	stack_name="tai-search-service-databases",
	description="Stack for the search service. This stack contains the document " \
    	"database, pinecone database, and search engine used by the tai platform.",
    duplicate_stack_for_development=False,
    **BASE_SETTINGS,
)
search_service: TaiSearchServiceStack = TaiSearchServiceStack(
    scope=app,
	config=search_service_config,
    doc_db_settings=DOCUMENT_DB_SETTINGS,
    pinecone_db_settings=PINECONE_DB_SETTINGS,
    search_service_settings=SEARCH_SERVICE_SETTINGS,
)


tai_api_config = StackConfigBaseModel(
    stack_id="tai-api",
    stack_name="tai-api",
    description="Stack for the tai api service. This stack contains the tai api service.",
    duplicate_stack_for_development=True,
    **BASE_SETTINGS,
)

tai_api: TaiApiStack = TaiApiStack(
    scope=app,
    config=tai_api_config,
    api_settings=TAI_API_SETTINGS,
    vpc=search_service.vpc,
)


frontend_server_config = StackConfigBaseModel(
    stack_id="tai-frontend-server",
    stack_name="tai-frontend-server",
    description="Stack for the frontend server of the T.A.I. service. This stack contains the " \
        "implementation of the required frontend resources.",
    duplicate_stack_for_development=True, # if we don't do this, you won't be able to delete the dev tai stack without destroying this one.
    **BASE_SETTINGS,
)
frontend_server: TaiFrontendServerStack = TaiFrontendServerStack(
    scope=app,
    config=frontend_server_config,
    data_transfer_bucket=search_service.documents_to_index_queue,
)


app.synth()
