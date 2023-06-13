import os
from aws_cdk import App, Environment
from tai_service.api.main import MyStack

# for development, use account/region from cdk cli
dev_env = Environment(
  account=os.getenv('CDK_DEFAULT_ACCOUNT'),
  region=os.getenv('CDK_DEFAULT_REGION')
)

app = App()
MyStack(app, "tai-service-dev", env=dev_env)
# MyStack(app, "tai-service-prod", env=prod_env)

app.synth()