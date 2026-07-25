from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApplicationError, ConflictError
from app.models.domain import (
    AuditEvent,
    SupplierOffer,
    SupplierOfferPriceTier,
    TestBuyOutcome,
    TestBuyRecommendation,
)
from app.modules.economics.schemas import (
    EconomicsScopeQuery,
    ProductReferenceResponse,
    ScopeResponse,
)
from app.modules.sourcing.kernel import OfferTier, TestBuyInputs, recommend_test_buy
from app.modules.sourcing.repository import SourcingRepository
from app.modules.sourcing.schemas import (
    PaginationResponse,
    SupplierOfferCreate,
    SupplierOfferListQuery,
    SupplierOfferListResponse,
    SupplierOfferResponse,
    SupplierOfferTierResponse,
    SupplierResponse,
    TestBuyEvidenceResponse,
    TestBuyNoticeResponse,
    TestBuyRequest,
    TestBuyResponse,
    TestBuyScenarioResponse,
)


class SourcingService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = SourcingRepository(session)

    def create_offer(
        self,
        query: EconomicsScopeQuery,
        command: SupplierOfferCreate,
        *,
        correlation_id: str | None,
    ) -> SupplierOfferResponse:
        marketplace = self._repository.ensure_scope(query.organisation_id, query.marketplace_id)
        product = self._repository.get_product(
            query.organisation_id, query.marketplace_id, command.product_id
        )
        if command.currency_code != marketplace.default_currency_code:
            raise ConflictError(
                "supplier_offer_currency_mismatch",
                (
                    "Supplier offer currency must match the marketplace currency until FX "
                    "assumptions exist"
                ),
                details={
                    "marketplace_currency_code": marketplace.default_currency_code,
                    "submitted_currency_code": command.currency_code,
                },
            )
        if command.quotation_date > datetime.now(UTC).date():
            raise ApplicationError(
                "supplier_offer_future_quotation",
                "quotation_date cannot be in the future",
            )
        supplier = self._repository.find_or_create_supplier(
            query.organisation_id, command.supplier_name
        )
        offer = SupplierOffer(
            id=str(uuid.uuid4()),
            organisation_id=query.organisation_id,
            marketplace_id=query.marketplace_id,
            supplier_id=supplier.id,
            product_id=product.id,
            supplier_name_at_quote=command.supplier_name,
            currency_code=command.currency_code,
            unit_cost=command.unit_cost,
            minimum_order_quantity=command.minimum_order_quantity,
            lead_time_days=command.lead_time_days,
            quotation_date=command.quotation_date,
            valid_until=(
                datetime.combine(command.valid_until, time.max, tzinfo=UTC)
                if command.valid_until is not None
                else None
            ),
            notes=command.notes,
        )
        offer.price_tiers = [
            SupplierOfferPriceTier(
                minimum_quantity=command.minimum_order_quantity,
                unit_cost=command.unit_cost,
            ),
            *[
                SupplierOfferPriceTier(
                    minimum_quantity=tier.minimum_quantity,
                    unit_cost=tier.unit_cost,
                )
                for tier in command.price_tiers
            ],
        ]
        self._session.add(offer)
        self._session.add(
            AuditEvent(
                organisation_id=query.organisation_id,
                actor_type="user",
                event_type="supplier_offer.recorded",
                entity_type="product_supplier_offer",
                entity_id=product.id,
                event_payload={
                    "supplier_offer_id": offer.id,
                    "supplier_id": supplier.id,
                    "quotation_date": command.quotation_date.isoformat(),
                    "tier_count": len(offer.price_tiers),
                },
                correlation_id=correlation_id,
            )
        )
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "supplier_offer_conflict",
                "The supplier or quotation changed concurrently; reload and try again",
            ) from exc
        self._session.refresh(offer)
        return _offer_response(offer)

    def list_offers(
        self, query: SupplierOfferListQuery, product_id: str
    ) -> SupplierOfferListResponse:
        self._repository.ensure_scope(query.organisation_id, query.marketplace_id)
        product = self._repository.get_product(
            query.organisation_id, query.marketplace_id, product_id
        )
        page = self._repository.list_offers(
            organisation_id=query.organisation_id,
            marketplace_id=query.marketplace_id,
            product_id=product.id,
            page=query.page,
            page_size=query.page_size,
        )
        total_pages = (
            (page.total_items + query.page_size - 1) // query.page_size if page.total_items else 0
        )
        return SupplierOfferListResponse(
            scope=ScopeResponse(
                organisation_id=query.organisation_id,
                marketplace_id=query.marketplace_id,
            ),
            product=ProductReferenceResponse(
                product_id=product.id,
                asin=product.asin,
                title=product.title,
            ),
            items=[_offer_response(offer) for offer in page.items],
            pagination=PaginationResponse(
                page=query.page,
                page_size=query.page_size,
                total_items=page.total_items,
                total_pages=total_pages,
                has_previous=query.page > 1 and page.total_items > 0,
                has_next=query.page < total_pages,
            ),
            comparison_dimensions=["unit_cost", "minimum_order_quantity", "lead_time_days"],
            selection_note=(
                "Offers are shown with price, MOQ and lead time. SellerOS does not select an offer "
                "using price alone."
            ),
        )

    def recommend_test_buy(
        self,
        query: EconomicsScopeQuery,
        product_id: str,
        command: TestBuyRequest,
        *,
        correlation_id: str | None,
    ) -> TestBuyResponse:
        self._repository.ensure_scope(query.organisation_id, query.marketplace_id)
        product = self._repository.get_product(
            query.organisation_id, query.marketplace_id, product_id
        )
        offer = self._repository.get_offer(
            organisation_id=query.organisation_id,
            marketplace_id=query.marketplace_id,
            product_id=product.id,
            offer_id=command.supplier_offer_id,
        )
        if command.budget_currency_code != offer.currency_code:
            raise ConflictError(
                "test_buy_currency_mismatch",
                (
                    "Budget currency must match the supplier offer; currency conversion is not "
                    "inferred"
                ),
                details={
                    "budget_currency_code": command.budget_currency_code,
                    "offer_currency_code": offer.currency_code,
                },
            )
        latest_snapshot = self._repository.latest_snapshot(product)
        observation_date_unconfirmed = (
            latest_snapshot is not None and latest_snapshot.observed_on is None
        )
        snapshot = (
            latest_snapshot
            if latest_snapshot is not None and latest_snapshot.observed_on is not None
            else None
        )
        confidence = self._repository.latest_confidence_score(
            snapshot.id if snapshot is not None else None
        )
        raw_monthly_demand = snapshot.monthly_sold if snapshot is not None else None
        monthly_demand = (
            raw_monthly_demand
            if raw_monthly_demand is not None and raw_monthly_demand >= 0
            else None
        )
        invalid_monthly_demand = raw_monthly_demand is not None and raw_monthly_demand < 0
        now = datetime.now(UTC)
        result = recommend_test_buy(
            TestBuyInputs(
                monthly_demand_units=monthly_demand,
                data_confidence_score=confidence.score_value if confidence is not None else None,
                lead_time_days=offer.lead_time_days,
                minimum_order_quantity=offer.minimum_order_quantity,
                budget_amount=command.budget_amount,
                budget_currency_code=command.budget_currency_code,
                offer_currency_code=offer.currency_code,
                price_tiers=tuple(
                    OfferTier(
                        minimum_quantity=tier.minimum_quantity,
                        unit_cost=tier.unit_cost,
                    )
                    for tier in offer.price_tiers
                ),
                offer_valid=offer.valid_until is None or offer.valid_until >= now,
            )
        )
        scenario_models = [
            TestBuyScenarioResponse(
                scenario=item.scenario,
                quantity=item.quantity,
                unit_cost=item.unit_cost,
                required_investment=item.required_investment,
                expected_sell_through_days=item.expected_sell_through_days,
                status=item.status,
                reason_codes=list(item.reason_codes),
            )
            for item in result.scenarios
        ]
        scenario_payload = [item.model_dump(mode="json") for item in scenario_models]
        demand_is_valid = monthly_demand is not None
        notice_reason_codes = (
            (*result.reason_codes, "TEST_BUY_MONTHLY_DEMAND_INVALID")
            if invalid_monthly_demand
            else result.reason_codes
        )
        if observation_date_unconfirmed:
            notice_reason_codes = (
                *notice_reason_codes,
                "TEST_BUY_OBSERVATION_DATE_UNCONFIRMED",
            )
        notice_models = _test_buy_notices(notice_reason_codes, demand_exists=demand_is_valid)
        evidence_model = TestBuyEvidenceResponse(
            source_snapshot_id=snapshot.id if snapshot is not None else None,
            monthly_demand_units=raw_monthly_demand,
            monthly_demand_label="estimated" if demand_is_valid else None,
            monthly_demand_source=(
                "keepa_monthly_sold" if raw_monthly_demand is not None else None
            ),
            market_snapshot_at=snapshot.snapshot_at if snapshot is not None else None,
            market_observed_on=snapshot.observed_on if snapshot is not None else None,
            data_confidence_score_result_id=confidence.id if confidence is not None else None,
            data_confidence_score=confidence.score_value if confidence is not None else None,
            data_confidence_label="calculated" if confidence is not None else None,
            data_confidence_formula_version=(
                confidence.formula_version if confidence is not None else None
            ),
        )
        outcome = (
            TestBuyOutcome.recommended
            if any(item.status == "recommended" for item in result.scenarios)
            else TestBuyOutcome.blocked
        )
        recommendation = TestBuyRecommendation(
            id=str(uuid.uuid4()),
            organisation_id=query.organisation_id,
            marketplace_id=query.marketplace_id,
            product_id=product.id,
            supplier_offer_id=offer.id,
            source_snapshot_id=snapshot.id if snapshot is not None else None,
            data_confidence_score_result_id=confidence.id if confidence is not None else None,
            budget_amount=command.budget_amount,
            budget_currency_code=command.budget_currency_code,
            formula_version=result.formula_version,
            configuration_checksum=result.configuration_checksum,
            inputs=result.inputs,
            evidence=evidence_model.model_dump(mode="json"),
            scenarios=scenario_payload,
            notices=[notice.model_dump(mode="json") for notice in notice_models],
            outcome=outcome,
            advisory_only=True,
        )
        self._session.add(recommendation)
        self._session.add(
            AuditEvent(
                organisation_id=query.organisation_id,
                actor_type="system",
                event_type="test_buy.evaluated",
                entity_type="test_buy_recommendation",
                entity_id=recommendation.id,
                event_payload={
                    "product_id": product.id,
                    "supplier_offer_id": offer.id,
                    "formula_version": result.formula_version,
                    "configuration_checksum": result.configuration_checksum,
                    "source_snapshot_id": recommendation.source_snapshot_id,
                    "data_confidence_score_result_id": (
                        recommendation.data_confidence_score_result_id
                    ),
                    "outcome": outcome.value,
                    "advisory_only": True,
                },
                correlation_id=correlation_id,
            )
        )
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "test_buy_persistence_conflict",
                "The advisory scenario could not be retained; reload and try again",
            ) from exc
        self._session.refresh(recommendation)
        return TestBuyResponse(
            id=recommendation.id,
            scope=ScopeResponse(
                organisation_id=query.organisation_id,
                marketplace_id=query.marketplace_id,
            ),
            product=ProductReferenceResponse(
                product_id=product.id,
                asin=product.asin,
                title=product.title or (snapshot.title if snapshot is not None else None),
            ),
            supplier_offer_id=offer.id,
            budget_amount=command.budget_amount,
            budget_currency_code=command.budget_currency_code,
            formula_version=result.formula_version,
            configuration_checksum=result.configuration_checksum,
            inputs=result.inputs,
            evidence=evidence_model,
            scenarios=scenario_models,
            notices=notice_models,
            outcome=outcome.value,
            decision_label="recommended" if outcome is TestBuyOutcome.recommended else None,
            created_at=recommendation.created_at,
        )


def _offer_response(offer: SupplierOffer) -> SupplierOfferResponse:
    return SupplierOfferResponse(
        id=offer.id,
        supplier=SupplierResponse(id=offer.supplier_id, name=offer.supplier_name_at_quote),
        product_id=offer.product_id,
        currency_code=offer.currency_code,
        unit_cost=offer.unit_cost,
        minimum_order_quantity=offer.minimum_order_quantity,
        lead_time_days=offer.lead_time_days,
        quotation_date=offer.quotation_date,
        valid_until=offer.valid_until.date() if offer.valid_until is not None else None,
        notes=offer.notes,
        price_tiers=[
            SupplierOfferTierResponse(
                minimum_quantity=tier.minimum_quantity,
                unit_cost=tier.unit_cost,
            )
            for tier in offer.price_tiers
        ],
        created_at=offer.created_at,
    )


def _test_buy_notices(
    reason_codes: tuple[str, ...], *, demand_exists: bool
) -> list[TestBuyNoticeResponse]:
    definitions: dict[
        str,
        tuple[
            Literal["missing", "warning"],
            str,
            Literal["estimated", "calculated", "recommended", "user_confirmed"],
        ],
    ] = {
        "TEST_BUY_MONTHLY_DEMAND_MISSING": (
            "missing",
            "A monthly-demand estimate is required before suggesting a test quantity.",
            "estimated",
        ),
        "TEST_BUY_MONTHLY_DEMAND_ZERO": (
            "warning",
            "Monthly demand is zero, so no test quantity is recommended.",
            "estimated",
        ),
        "TEST_BUY_MONTHLY_DEMAND_INVALID": (
            "missing",
            "Imported monthly demand is negative and was excluded from the recommendation.",
            "estimated",
        ),
        "TEST_BUY_DATA_CONFIDENCE_MISSING": (
            "missing",
            "A calculated data-confidence score is required.",
            "calculated",
        ),
        "TEST_BUY_OBSERVATION_DATE_UNCONFIRMED": (
            "missing",
            (
                "The latest legacy snapshot has no user-confirmed market observation date "
                "and was excluded from this recommendation."
            ),
            "estimated",
        ),
        "TEST_BUY_BUDGET_ZERO": (
            "warning",
            "Budget is zero, so no units can be recommended.",
            "user_confirmed",
        ),
        "TEST_BUY_OFFER_EXPIRED": (
            "warning",
            "The supplier quotation has expired; request a current quotation.",
            "user_confirmed",
        ),
        "TEST_BUY_LOW_CONFIDENCE_CAP_APPLIED": (
            "warning",
            "Low confidence capped the proposed quantity.",
            "recommended",
        ),
        "TEST_BUY_MOQ_EXCEEDS_CONFIDENCE_CAP": (
            "warning",
            "Supplier MOQ exceeds the safe low-confidence quantity cap.",
            "recommended",
        ),
        "TEST_BUY_BUDGET_BELOW_MOQ": (
            "warning",
            "The budget cannot fund the supplier MOQ.",
            "recommended",
        ),
        "TEST_BUY_BUDGET_CAP_APPLIED": (
            "warning",
            "The budget capped the demand-based quantity.",
            "recommended",
        ),
    }
    notices: list[TestBuyNoticeResponse] = []
    if demand_exists:
        notices.append(
            TestBuyNoticeResponse(
                code="TEST_BUY_DEMAND_IS_ESTIMATED",
                severity="warning",
                message="Monthly demand is an imported estimate, not observed unit sales.",
                evidence_label="estimated",
            )
        )
    for code in dict.fromkeys(reason_codes):
        definition = definitions.get(code)
        if definition is None:
            continue
        severity, message, label = definition
        notices.append(
            TestBuyNoticeResponse(
                code=code,
                severity=severity,
                message=message,
                evidence_label=label,
            )
        )
    return notices
