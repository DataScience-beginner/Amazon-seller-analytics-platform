from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.portfolio.schemas import (
    DashboardResponse,
    DatasetOverviewQuery,
    DatasetOverviewResponse,
    PortfolioScopeQuery,
    ProductDetailResponse,
    ProductListQuery,
    ProductListResponse,
)
from app.modules.portfolio.service import PortfolioService

router = APIRouter(tags=["portfolio"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Read the tenant-scoped executive portfolio dashboard",
)
def get_dashboard(
    query: Annotated[PortfolioScopeQuery, Query()],
    session: Annotated[Session, Depends(get_db)],
) -> DashboardResponse:
    return PortfolioService(session).dashboard(query)


@router.get(
    "/dashboard/dataset-overview",
    response_model=DatasetOverviewResponse | None,
    summary="Read a tenant-scoped dataset overview with an optional category filter",
)
def get_dataset_overview(
    query: Annotated[DatasetOverviewQuery, Query()],
    session: Annotated[Session, Depends(get_db)],
) -> DatasetOverviewResponse | None:
    return PortfolioService(session).dataset_overview(query)


@router.get(
    "/products",
    response_model=ProductListResponse,
    summary="Search, filter, sort, and paginate the product portfolio",
)
def get_products(
    query: Annotated[ProductListQuery, Query()],
    session: Annotated[Session, Depends(get_db)],
) -> ProductListResponse:
    return PortfolioService(session).list_products(query)


@router.get(
    "/products/{product_id}",
    response_model=ProductDetailResponse,
    summary="Read product metrics and recommendation evidence",
)
def get_product(
    product_id: Annotated[
        str,
        Path(
            min_length=1,
            max_length=36,
            pattern=r"^[^/\\]+$",
            description="SellerOS product identifier",
        ),
    ],
    query: Annotated[PortfolioScopeQuery, Query()],
    session: Annotated[Session, Depends(get_db)],
) -> ProductDetailResponse:
    return PortfolioService(session).get_product(query, product_id)
