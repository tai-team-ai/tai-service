"""Define metrics utilities and classes for retrieving and aggregating metrics for the TAIService API."""
from typing import Optional, Union, Type
from datetime import datetime
from uuid import UUID
from pydantic import Field, conint

from ...api.taibackend.shared_schemas import BasePydanticModel, DateRange
from .shared_schemas import UsageMetric
from .databases.document_db_schemas import ClassResourceChunkDocument, ClassResourceDocument
from .databases.document_db import DocumentDB, USAGE_LOG_FIELD_NAME


class MetricsConfig(BasePydanticModel):
    """Define the metrics config."""
    document_db_instance: DocumentDB = Field(
        ...,
        description="The instance of the document db.",
    )

    class Config:
        """Define the config for the metrics config."""
        arbitrary_types_allowed = True


class BaseFrequentlyAccessedObjects(BasePydanticModel):
    """Define a base schema for common resources."""
    class_id: UUID = Field(
        ...,
        description="The ID that the common resource belongs to.",
    )
    date_range: DateRange = Field(
        default_factory=DateRange,
        description="The date range over which the appearances of the common resource are counted.",
    )


class BaseFrequentlyAccessedObject(BasePydanticModel):
    """Define a base schema for ranked common resources."""
    rank: int = Field(
        ...,
        ge=1,
        description="The rank of the object when ranked by appearances during the date range.",
    )
    appearances_during_period: int = Field(
        ...,
        ge=1,
        description="The number of times the object appeared during the date range.",
    )


class FrequentlyAccessedResource(BaseFrequentlyAccessedObject):
    """Define a schema for a common resource."""
    resource: ClassResourceDocument = Field(
        ...,
        description="The resource that was most common during the date range.",
    )


class FrequentlyAccessedResources(BaseFrequentlyAccessedObjects):
    """Define a schema for common resources."""
    resources: list[FrequentlyAccessedResource] = Field(
        ...,
        description="The list of the most frequently accessed resources during the date range.",
    )


class Metrics:
    """Define the metrics class."""
    def __init__(self, config: MetricsConfig):
        """Initialize the metrics class."""
        self._doc_db = config.document_db_instance

    def upsert_metrics_for_docs(self, ids: list[UUID],  DocClass: Union[Type[ClassResourceChunkDocument], Type[ClassResourceDocument]]) -> None:
        """Upsert the metrics of the class resource."""
        for doc_id in ids:
            metric = UsageMetric(timestamp=datetime.utcnow())
            self._doc_db.upsert_metric(doc_id, metric, DocClass)

    def get_most_frequently_accessed_resources(
        self,
        class_id: UUID,
        date_range: Optional[DateRange] = None,
        top_level_doc: bool = False,
    ) -> FrequentlyAccessedResources:
        """Get the most frequently accessed resources."""
        if date_range is None:
            date_range = DateRange()
        pipeline_usage = [
            {
                '$match': {
                    'class_id': str(class_id),
                }
            },
            {
                '$match': {
                    '$and': [
                        { 'child_resource_ids' if top_level_doc else 'parent_resource_ids': { '$exists': True } },
                        { 'child_resource_ids' if top_level_doc else 'parent_resource_ids': { '$ne': [] } },
                    ]
                },
            },
            {
                '$unwind': f'${USAGE_LOG_FIELD_NAME}'
            },
            {
                '$match': {
                    f'{USAGE_LOG_FIELD_NAME}.timestamp': {'$gte': date_range.start_date, '$lte': date_range.end_date} ,
                },
            },
            {
                '$group': {
                    '_id': '$_id',
                    'resource_count': {'$sum': 1 },
                }
            },
            {
                '$sort': {'resource_count': -1}
            }
        ]
        resources_usage = list(self._doc_db.run_aggregate_query(pipeline_usage, ClassResourceDocument))
        ids = [resource_usage['_id'] for resource_usage in resources_usage] 
        frequently_accessed_resources: list[FrequentlyAccessedResource] = []
        for rank, doc_id in enumerate(ids, 1):
            document = self._doc_db.find_one(doc_id, ClassResourceDocument)
            frequently_accessed_resources.append(FrequentlyAccessedResource(
                rank=rank,
                appearances_during_period=resources_usage[rank - 1]['resource_count'],
                resource=document,
            ))
        frequently_accessed_resources = FrequentlyAccessedResources(
            class_id=class_id,
            date_range=DateRange(
                start_date=date_range.start_date,
                end_date=date_range.end_date,
            ),
            resources=[resource.dict() for resource in frequently_accessed_resources]
        )
        return frequently_accessed_resources
