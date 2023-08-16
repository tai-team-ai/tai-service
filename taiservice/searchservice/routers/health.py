"""Define endpoints to test the health of the service."""
from fastapi import APIRouter
import torch


ROUTER = APIRouter()
ROUTER.get("/health-check")(lambda: {"status": "ok"})
ROUTER.get("/")(lambda: {"message": "Welcome to the T.A.I. Service API!"})
ROUTER.get("/cuda", include_in_schema=False)(lambda: {"cuda available": torch.cuda.is_available()})
