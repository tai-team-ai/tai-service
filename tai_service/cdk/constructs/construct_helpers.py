"""Define helper functions for CDK constructs."""
from typing import Any, Optional, Union
import re
from constructs import Construct
from loguru import logger
from aws_cdk import (
    aws_ec2 as ec2,
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

def _