from fastapi import APIRouter

from app.api.v1 import extract, parse, review

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(parse.router)
api_router.include_router(extract.router)
api_router.include_router(review.router)
