"""Define endpoints that get common resources and questions from the database."""
from fastapi import APIRouter, Request
# first imports are for local development, second imports are for deployment
try:
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
    from ..taibackend.backend import Backend
    from .common_resources_schema import FrequentlyAccessedResources, CommonQuestions, CommonQuestion
except ImportError:
    from runtime_settings import BACKEND_ATTRIBUTE_NAME
    from taibackend.backend import Backend
    from routers.common_resources_schema import FrequentlyAccessedResources, CommonQuestions, CommonQuestion


ROUTER = APIRouter()


@ROUTER.get("/frequently-accessed-resources/{class_id}", response_model=FrequentlyAccessedResources)
def get_frequently_accessed_resources(request: Request, class_id: str):
    """
    Get frequently accessed resources for a specific class."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return backend.get_frequently_accessed_class_resources(class_id)


@ROUTER.get("/common-questions/{class_id}", response_model=CommonQuestions)
def get_common_questions(request: Request, class_id: str):
    """Get all common questions."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    # return backend.get_frequently_asked_questions(class_id)
    dummy_response = CommonQuestions(
        common_questions=[
                CommonQuestion(rank=1, appearances_during_period=10, question="What is the meaning of life?"),
                CommonQuestion(rank=2, appearances_during_period=8, question="How do I reset my password?"),
                CommonQuestion(rank=3, appearances_during_period=6, question="What programming languages does your platform support?"),
                CommonQuestion(rank=4, appearances_during_period=4, question="Can I change my username?"),
                CommonQuestion(rank=5, appearances_during_period=2, question="How can I contact customer support?")
            ],
        class_id=class_id,
        
    )
    return dummy_response
