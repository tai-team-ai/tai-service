"""
Define a private bucket construct.

This construct create a private bucket that allows replication
and control over the removal policy.
"""

from typing import Optional, Union
from constructs import Construct
from pydantic import BaseModel, root_validator, Field
from aws_cdk import (
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
    aws_iam as iam,
)


class   VersionedBucketConfigModel(BaseModel):
    """Define the configuration for the bucket construct."""

    bucket_name: str = Field(
        ...,
        description="The name of the bucket to create.",
    )
    bucket: s3.Bucket = Field(
        default=None,
        description="An existing bucket to use.",
    )
    removal_policy: Optional[RemovalPolicy] = Field(
        default=RemovalPolicy.RETAIN,
        description="The removal policy for the bucket.",
    )
    lifecycle_rules: Optional[list[s3.LifecycleRule]] = Field(
        default=s3.LifecycleRule(
            id="DeleteOldVersions",
            noncurrent_versions_to_retain=1,
            noncurrent_version_expiration=Duration.days(1),
        ),
        description="The lifecycle rules for the bucket.",
    )
    public_read_access: bool = Field(
        default=False,
        description="Whether or not to allow public read access.",
    )
    delete_objects_on_bucket_removal: bool = Field(
        default=False,
        description="Whether or not to automatically delete objects on removal.",
    )

    class Config:
        """Define the Pydantic model configuration."""

        arbitrary_types_allowed = True

    @root_validator
    def validate_bucket(cls, values) -> dict:
        """Validate that only one bucket is defined."""
        if values["bucket"] is None and values["bucket_name"] is None:
            raise ValueError("Must define either bucket or bucket_name")
        return values


class VersionedBucket(Construct):
    """
    Define a private bucket construct.

    This construct allows for easy replication of a bucket with a
    defined removal policy.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: VersionedBucketConfigModel,
        **kwargs,
    ) -> None:
        """Initialize the construct."""
        super().__init__(scope, construct_id, **kwargs)
        self._config = config
        if config.bucket:
            self.bucket = config.bucket
        else:
            public_access = s3.BlockPublicAccess(
                block_public_acls=True,
                block_public_policy=False if config.public_read_access else True,
                ignore_public_acls=True,
                restrict_public_buckets=False if config.public_read_access else True,
            )
            self.bucket = s3.Bucket(
                self,
                construct_id,
                bucket_name=config.bucket_name,
                removal_policy=config.removal_policy,
                auto_delete_objects=config.delete_objects_on_bucket_removal,
                encryption=s3.BucketEncryption.S3_MANAGED,
                block_public_access=public_access,
                public_read_access=config.public_read_access,
                versioned=True,
                metrics=[self._create_metrics_for_bucket()],
                lifecycle_rules=[
                    s3.LifecycleRule(
                        id="DeleteOldVersions",
                        noncurrent_versions_to_retain=1,
                        noncurrent_version_expiration=Duration.days(30),
                    ),
                ],
            )

    @property
    def bucket_name(self) -> str:
        """Return the bucket name."""
        return self.bucket.bucket_name

    def _create_metrics_for_bucket(self) -> s3.BucketMetrics:
        """Create metrics for the bucket."""
        metrics = s3.BucketMetrics(
            id=f"{self._config.bucket_name}-Metrics",
            tag_filters={
                "Bucket": self._config.bucket_name,
            },
        )
        return metrics

    def update_removal_policy(self, removal_policy: RemovalPolicy) -> None:
        """Update the removal policy for the bucket."""
        self.bucket.apply_removal_policy(removal_policy)

    def grant_read_access(self, role: iam.Role) -> None:
        """Grant read access to the bucket."""
        self.bucket.grant_read(role)

    def grant_write_access(self, role: iam.Role) -> None:
        """Grant write access to the bucket."""
        self.bucket.grant_write(role)

    def grant_read_write_access(self, role: iam.Role) -> None:
        """Grant read and write access to the bucket."""
        self.bucket.grant_read_write(role)

    def replicate_to_destination_bucket(
        self,
        destinantion_bucket: Union[s3.Bucket, str],
        destination_aws_account_id: str,
    ) -> None:
        """Replicate the bucket to another bucket."""
        if isinstance(destinantion_bucket, str):
            destination_bucket = s3.Bucket.from_bucket_name(
                self,
                f"{self.bucket.node.id}-DestinationBucket",
                destinantion_bucket,
            )
        
        replication_role = iam.Role(
            self,
            f"{self.bucket.node.id}-ReplicationRole",
            assumed_by=iam.ServicePrincipal("s3.amazonaws.com"),
            description="Role for replicating the bucket",
            path="/service-role/",
        )
        replication_role.add_to_policy(
            iam.PolicyStatement(
                resources=[self.bucket.bucket_arn],
                actions=["s3:GetReplicationConfiguration", "s3:ListBucket"],
            )
        )
        replication_role.add_to_policy(
            iam.PolicyStatement(
                resources=[destination_bucket.arn_for_objects("*")],
                actions=[
                    "s3:ReplicateObject",
                    "s3:ReplicateDelete",
                    "s3:ReplicateTags",
                    "s3:GetObjectVersionTagging",
                    "s3:ObjectOwnerOverrideToBucketOwner",
                ],
            )
        )
        self.bucket.add_to_policy(
            iam.PolicyStatement(
                resources=[destination_bucket.arn_for_objects("*")],
                actions=[
                    "s3:GetObjectVersionTagging",
                    "s3:GetObjectVersion",
                    "s3:GetObjectVersionAcl",
                    "s3:GetObjectVersionForReplication",
                    "s3:GetObjectLegalHold",
                    "s3:GetObjectRetention",
                ],
            )
        )
        self.bucket.node.default_child.replication_configuration = s3.CfnBucket.ReplicationConfigurationProperty(
            role=replication_role.role_arn,
            rules=[
                s3.CfnBucket.ReplicationRuleProperty(
                    destination=s3.CfnBucket.ReplicationDestinationProperty(
                        bucket=destination_bucket.bucket_arn,
                        account=destination_aws_account_id,
                    ),
                    status="Enabled",
                    priority=1,
                ),
            ],
            
        )

    def replicate_from_bucket(self, source_bucket_aws_account_id: str) -> None:
        """Replicate the bucket from another bucket."""
        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="SourceAccessToReplicateIntoBucket",
                resources=[self.bucket.arn_for_objects("*")],
                effect=iam.Effect.ALLOW,
                principals=[iam.AccountPrincipal(source_bucket_aws_account_id)],
                actions=[
                    "s3:ReplicateObject",
                    "s3:ReplicateDelete",
                    "s3:ReplicateTags",
                    "s3:GetObjectVersionTagging",
                    "s3:ObjectOwnerOverrideToBucketOwner",
                ],
            )
        )
        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="SourceAccessToVersioning",
                effect=iam.Effect.ALLOW,
                principals=[iam.AccountPrincipal(source_bucket_aws_account_id)],
                actions=["s3:GetBucketVersioning", "s3:PutBucketVersioning"],
                resources=[self.bucket.bucket_arn],
            ),
        )
