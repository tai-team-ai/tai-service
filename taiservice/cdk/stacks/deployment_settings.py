"""Define base settings for the deployment."""
import os
from dotenv import load_dotenv
from aws_cdk import RemovalPolicy
from tai_aws_account_bootstrap.stack_config_models import (
    AWSDeploymentSettings,
    DeploymentType,
)


load_dotenv() # for .env file for VPC_ID


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
VPC_ID = os.environ.get("VPC_ID")
