from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.economics.schemas import EconomicsScopeQuery
from app.modules.sourcing.schemas import (
    SupplierOfferCreate,
    SupplierOfferListQuery,
    SupplierOfferListResponse,
    SupplierOfferResponse,
    TestBuyRequest,
    TestBuyResponse,
)
from app.modules.sourcing.service import SourcingService

router = APIRouter(tags=["sourcing"])
ProductIdPath = Annotated[
    str,
    Path(min_length=1, max_length=36, pattern=r"^[^/\\]+$"),
]


@router.get(
    "/products/{product_id}/supplier-offers",
    response_model=SupplierOfferListResponse,
    summary="List bounded supplier quotations without price-only selection",
)
def get_supplier_offers(
    product_id: ProductIdPath,
    query: Annotated[SupplierOfferListQuery, Query()],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierOfferListResponse:
    return SourcingService(session).list_offers(query, product_id)


@router.post(
    "/supplier-offers",
    response_model=SupplierOfferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an immutable supplier quotation and its price tiers",
)
def create_supplier_offer(
    command: SupplierOfferCreate,
    query: Annotated[EconomicsScopeQuery, Query()],
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> SupplierOfferResponse:
    return SourcingService(session).create_offer(
        query,
        command,
        correlation_id=getattr(request.state, "correlation_id", None),
    )


@router.post(
    "/products/{product_id}/test-buy-scenarios",
    response_model=TestBuyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and retain three advisory test-buy scenarios",
)
def create_test_buy_scenarios(
    product_id: ProductIdPath,
    command: TestBuyRequest,
    query: Annotated[EconomicsScopeQuery, Query()],
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> TestBuyResponse:
    return SourcingService(session).recommend_test_buy(
        query,
        product_id,
        command,
        correlation_id=getattr(request.state, "correlation_id", None),
    )
