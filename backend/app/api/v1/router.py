from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.modules.imports.api import router as imports_router
from app.modules.portfolio.api import router as portfolio_router
from app.modules.workspaces.api import router as workspaces_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(workspaces_router)
api_router.include_router(imports_router)
api_router.include_router(portfolio_router)
