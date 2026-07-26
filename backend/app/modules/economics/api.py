from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.economics.schemas import (
    CostProfileCreate,
    CostProfileResponse,
    EconomicsScopeQuery,
    ProductEconomicsResponse,
)
from app.modules.economics.service import EconomicsService

router = APIRouter(tags=["economics"])


@router.post(
    "/cost-profiles",
    response_model=CostProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an effective-dated seller cost-profile revision",
)
def create_cost_profile(
    command: CostProfileCreate,
    scope: Annotated[EconomicsScopeQuery, Query()],
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> CostProfileResponse:
    return EconomicsService(session).create_cost_profile(
        scope,
        command,
        correlation_id=getattr(request.state, "correlation_id", None),
    )


@router.get(
    "/products/{product_id}/economics",
    response_model=ProductEconomicsResponse,
    summary="Read effective costs and traced unit economics for one scoped product",
)
def get_product_economics(
    product_id: Annotated[
        str,
        Path(min_length=1, max_length=36, pattern=r"^[^/\\]+$"),
    ],
    scope: Annotated[EconomicsScopeQuery, Query()],
    session: Annotated[Session, Depends(get_db)],
) -> ProductEconomicsResponse:
    return EconomicsService(session).get_product_economics(scope, product_id)
