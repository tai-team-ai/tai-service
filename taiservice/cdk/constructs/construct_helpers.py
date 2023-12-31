"""Define helper functions for CDK constructs."""
import hashlib
import json
from pathlib import Path
from typing import Any, Optional, Union
import re
from constructs import Construct
import boto3
from loguru import logger
from aws_cdk import (
    aws_ec2 as ec2,
    Token,
    TagManager,
)


def implements_vpc_protocol(obj: Any) -> bool:
    """Return True if the object implements the VPC protocol."""
    required_attributes = [
        "availability_zones",
        "env",
        "internet_connectivity_established",
        "isolated_subnets",
        "node",
        "private_subnets",
        "public_subnets",
        "stack",
        "vpc_arn",
        "vpc_cidr_block",
        "vpc_id",
        "vpn_gateway_id"
    ]
    required_methods = [
        "add_client_vpn_endpoint",
        "add_flow_log",
        "add_gateway_endpoint",
        "add_interface_endpoint",
        "add_vpn_connection",
        "apply_removal_policy",
        "enable_vpn_gateway",
        "select_subnets"
    ]
    
    # Check if all required attributes and methods exist on the object
    for attr in required_attributes:
        if not hasattr(obj, attr):
            return False
    
    for method in required_methods:
        if not callable(getattr(obj, method, None)):
            return False
    
    return True

def get_vpc(scope: Construct, vpc: Optional[Union[str, ec2.IVpc]]) -> Optional[ec2.IVpc]:
    """Return the VPC object."""
    is_vpc_id = isinstance(vpc, str) and vpc.startswith("vpc-")
    if is_vpc_id:
        return ec2.Vpc.from_lookup(scope, "VPC", vpc_id=vpc)
    if implements_vpc_protocol(vpc) or not vpc:
        return vpc
    raise ValueError(f"VPC must be a VPC ID or an object that implements the VPC protocol. You provided: {vpc}")

def validate_vpc(vpc) -> Optional[Union[ec2.IVpc, str]]:
    if vpc:
        is_valid_vpc_id = isinstance(vpc, str) and vpc.startswith("vpc-")
        if is_valid_vpc_id or implements_vpc_protocol(vpc):
            return vpc
        elif isinstance(vpc, str):
            raise ValueError(f"Invalid VPC ID: {vpc}. Valid VPC IDs start with 'vpc-'")
        else:
            raise ValueError(f"Invalid VPC: {vpc}. Must be a string or implement protocol IVpc")
    return None

def sanitize_name(name: str, truncation_length: int = 63) -> str:
    """Return a sanitized name."""
    name = re.sub(r"[^a-zA-Z0-9-]", "-", name)
    if len(name) > truncation_length:
        logger.warning(
            f"Name {name} is longer than {truncation_length} characters. It will be truncated to {name[:truncation_length]}"
        )
    return name[:truncation_length]

def get_hash_for_all_files_in_dir(dir_path: Path) -> str:
    """Return a hash of all files in a directory."""
    hash_string = ""
    for file_path in dir_path.glob("**/*"):
        if file_path.is_file():
            with open(file_path, "rb") as file:
                bytes_buffer = file.read()
                hash_string += hashlib.md5(bytes_buffer).hexdigest()
    hash_string = hashlib.md5(hash_string.encode("utf-8")).hexdigest()
    return hash_string

def get_secret_arn_from_name(secret_name: str) -> str:
    """Get the ARN of a secret from its name.

    Args:
        deployment_settings (AWSDeploymentSettings): The deployment settings for the stack.
        secret_name (str): The name of the secret to get the ARN for.

    Returns:
        str: The ARN of the secret.
    """
    client = boto3.client("secretsmanager")
    response = client.describe_secret(SecretId=secret_name)
    return response["ARN"]

def retrieve_secret(secret_name: str) -> str:
    """Retrieve a secret from AWS Secrets Manager.

    Args:
        deployment_settings (AWSDeploymentSettings): The deployment settings for the stack.
        secret_name (str): The name of the secret to retrieve.

    Returns:
        str: The value of the secret.
    """
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    # try converting to dict with json loads
    secret =  response["SecretString"]
    try:
        secret = json.loads(secret)
    except:
        pass
    return secret


def create_restricted_security_group(scope: Construct, name: str, description: str, vpc: ec2.IVpc) -> ec2.SecurityGroup:
    """Create the security groups for the cluster."""
    security_group: ec2.SecurityGroup = ec2.SecurityGroup(
        scope,
        id=name + "-sg",
        security_group_name=name,
        description=description,
        vpc=vpc,
        allow_all_outbound=False,
    )
    return security_group


def vpc_interface_exists(service: ec2.InterfaceVpcEndpointAwsService, vpc: ec2.IVpc) -> bool:
    """Create an interface VPC endpoint.

    Args:
        service: The service to create the endpoint for.
        security_group: The security group to attach to the endpoint.
        vpc: The VPC to create the endpoint in.

    Returns:
        ec2.InterfaceVpcEndpoint: The interface VPC endpoint.
    """
    # check if the endpoint already exists with boto3
    client = boto3.client("ec2")
    # get the name form the Tags of the VPC
    vpc_id = getattr(vpc, "vpc_id")
    vpc_name = vpc.to_string().split("/")[0]
    if not vpc_id:
        response = client.describe_vpcs(Filters=[{"Name": "tag:Name", "Values": [vpc_name]}])
        vpcs = response["Vpcs"]
        if vpcs and vpcs[0].get("VpcId"):
            vpc_id = vpcs[0]["VpcId"]
        logger.warning(f"VPC ID not found for '{vpc_name}'. Cannot check if interface VPC endpoint exists.")
    response = client.describe_vpc_endpoints(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    for endpoint in response["VpcEndpoints"]:
        current_service_short_name = endpoint["ServiceName"].split(".")[-1]
        if service.short_name == current_service_short_name:
            logger.info(f"Interface VPC endpoint for {service.short_name} exists in '{vpc_name}' ({vpc_id})")
            return True
        logger.warning(f"Interface VPC endpoint for {service.short_name} does NOT exist in '{vpc_name}' ({vpc_id})")
        return False
    return True
