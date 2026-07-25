from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.domain import AuditEvent, CostProfile, ProductSnapshot
from app.modules.economics.repository import EconomicsRepository
from app.modules.economics.schemas import (
    CostProfileAuditResponse,
    CostProfileCreate,
    CostProfileResponse,
    EconomicsCalculationResponse,
    EconomicsNoticeResponse,
    EconomicsOutputsResponse,
    EconomicsScopeQuery,
    FeeEvidenceResponse,
    ObservedPriceResponse,
    ProductEconomicsResponse,
    ProductReferenceResponse,
    ProfilesByScopeResponse,
    ScopeResponse,
)
from app.modules.profitability import EconomicsInputs, calculate_unit_economics


class EconomicsService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = EconomicsRepository(session)

    def create_cost_profile(
        self,
        scope: EconomicsScopeQuery,
        command: CostProfileCreate,
        *,
        correlation_id: str | None,
    ) -> CostProfileResponse:
        marketplace = self._repository.ensure_scope(scope.organisation_id, scope.marketplace_id)
        product = (
            self._repository.get_product(
                scope.organisation_id, scope.marketplace_id, command.product_id
            )
            if command.product_id is not None
            else None
        )
        if command.currency_code != marketplace.default_currency_code:
            raise ConflictError(
                "cost_profile_currency_mismatch",
                (
                    "Cost profile currency must match the marketplace currency until FX "
                    "assumptions exist"
                ),
                details={
                    "marketplace_currency_code": marketplace.default_currency_code,
                    "submitted_currency_code": command.currency_code,
                },
            )
        scope_key = product.id if product is not None else "marketplace_default"
        previous = self._repository.current_revision(
            scope.organisation_id, scope.marketplace_id, scope_key
        )
        effective_from = command.effective_from.astimezone(UTC)
        if previous is not None and effective_from <= previous.effective_from:
            raise ConflictError(
                "cost_profile_effective_date_conflict",
                "A revision must become effective after the current revision",
                details={"current_effective_from": previous.effective_from.isoformat()},
            )
        version = 1 if previous is None else previous.version + 1
        if previous is not None:
            previous.effective_to = effective_from

        checksum = _profile_checksum(command, scope_key=scope_key, version=version)
        profile = CostProfile(
            id=str(uuid.uuid4()),
            organisation_id=scope.organisation_id,
            marketplace_id=scope.marketplace_id,
            product_id=product.id if product is not None else None,
            profile_scope_key=scope_key,
            version=version,
            supersedes_profile_id=previous.id if previous is not None else None,
            currency_code=command.currency_code,
            selling_price_tax_basis=command.selling_price_tax_basis,
            supplier_unit_cost=command.purchase_cost,
            freight_cost=command.freight_cost,
            prep_packaging_cost=command.prep_cost + command.packaging_cost,
            prep_cost=command.prep_cost,
            packaging_cost=command.packaging_cost,
            gst_rate_percent=command.gst_rate_percent,
            gst_recoverable_percent=command.gst_recoverable_percent,
            advertising_rate_percent=command.advertising_rate_percent,
            returns_rate_percent=command.returns_rate_percent,
            overhead_cost=command.overhead_cost,
            referral_fee_rate_percent=command.referral_fee_rate_percent,
            fulfilment_fee=command.fulfilment_fee,
            closing_fee=command.closing_fee,
            storage_fee=command.storage_fee,
            fee_source=command.fee_source,
            fee_effective_at=(
                command.fee_effective_at.astimezone(UTC)
                if command.fee_effective_at is not None
                else None
            ),
            fee_status=command.fee_status,
            minimum_margin_percent=command.minimum_margin_percent,
            target_margin_percent=command.target_margin_percent,
            configuration_checksum=checksum,
            effective_from=effective_from,
        )
        self._session.add(profile)
        event = AuditEvent(
            organisation_id=scope.organisation_id,
            actor_type="user",
            event_type="cost_profile.revised" if previous is not None else "cost_profile.created",
            entity_type="cost_profile_scope",
            entity_id=product.id if product is not None else scope.marketplace_id,
            event_payload={
                "profile_id": profile.id,
                "profile_version": profile.version,
                "scope": "product" if product is not None else "marketplace_default",
                "configuration_checksum": checksum,
                "selling_price_tax_basis": command.selling_price_tax_basis.value,
            },
            correlation_id=correlation_id,
        )
        self._session.add(event)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "cost_profile_revision_conflict",
                "The cost profile was revised concurrently; reload and try again",
            ) from exc
        self._session.refresh(profile)
        return _profile_response(profile)

    def get_product_economics(
        self, scope: EconomicsScopeQuery, product_id: str
    ) -> ProductEconomicsResponse:
        marketplace = self._repository.ensure_scope(scope.organisation_id, scope.marketplace_id)
        product = self._repository.get_product(
            scope.organisation_id, scope.marketplace_id, product_id
        )
        snapshot = self._repository.get_latest_snapshot(product)
        now = datetime.now(UTC)
        product_profile, marketplace_default_profile = self._repository.resolve_profiles_by_scope(
            organisation_id=scope.organisation_id,
            marketplace_id=scope.marketplace_id,
            product_id=product.id,
            as_of=now,
        )
        profile: CostProfile | None
        profile_source: Literal["product", "marketplace_default"] | None
        if product_profile is not None:
            profile = product_profile
            profile_source = "product"
        elif marketplace_default_profile is not None:
            profile = marketplace_default_profile
            profile_source = "marketplace_default"
        else:
            profile = None
            profile_source = None
        history = self._repository.profile_history(
            organisation_id=scope.organisation_id,
            marketplace_id=scope.marketplace_id,
            product_id=product.id,
        )
        observed_price = _observed_price(snapshot)
        notices: list[EconomicsNoticeResponse] = []
        observation_date_unconfirmed = snapshot is not None and snapshot.observed_on is None
        if observation_date_unconfirmed:
            notices.append(
                EconomicsNoticeResponse(
                    code="ECONOMICS_OBSERVATION_DATE_UNCONFIRMED",
                    severity="missing",
                    message=(
                        "The latest legacy snapshot has no user-confirmed market observation "
                        "date and was excluded from economics."
                    ),
                    evidence_label="observed",
                )
            )
        calculation: EconomicsCalculationResponse | None = None
        if profile is None:
            notices.append(
                EconomicsNoticeResponse(
                    code="ECONOMICS_COST_PROFILE_MISSING",
                    severity="missing",
                    message="No effective product or marketplace-default cost profile exists.",
                    evidence_label="user_confirmed",
                )
            )
        else:
            selling_price: Decimal | None = None
            if observed_price is None:
                if not observation_date_unconfirmed:
                    notices.append(
                        EconomicsNoticeResponse(
                            code="ECONOMICS_SELLING_PRICE_MISSING",
                            severity="missing",
                            message=(
                                "The latest snapshot has no observed selling price and currency."
                            ),
                            evidence_label="observed",
                        )
                    )
            elif observed_price.amount < 0:
                notices.append(
                    EconomicsNoticeResponse(
                        code="ECONOMICS_SELLING_PRICE_INVALID",
                        severity="warning",
                        message=(
                            "The latest imported selling price is negative and was excluded from "
                            "the calculation."
                        ),
                        evidence_label="observed",
                    )
                )
            elif observed_price.currency_code != profile.currency_code:
                notices.append(
                    EconomicsNoticeResponse(
                        code="ECONOMICS_CURRENCY_MISMATCH",
                        severity="warning",
                        message=(
                            "Observed price and cost profile currencies differ; they were not "
                            "combined."
                        ),
                        evidence_label="observed",
                    )
                )
            else:
                selling_price = observed_price.amount
            result = calculate_unit_economics(_economics_inputs(profile, selling_price))
            calculation = EconomicsCalculationResponse(
                formula_version=result.formula_version,
                configuration_checksum=result.configuration_checksum,
                status=result.status,
                selling_price_tax_basis=profile.selling_price_tax_basis,
                inputs=result.inputs,
                formulas=result.formulas,
                outputs=EconomicsOutputsResponse(
                    landed_cost=result.outputs.landed_cost,
                    net_revenue=result.outputs.net_revenue,
                    output_gst=result.outputs.output_gst,
                    amazon_fees=result.outputs.amazon_fees,
                    contribution_profit=result.outputs.contribution_profit,
                    margin_percent=result.outputs.margin_percent,
                    roi_percent=result.outputs.roi_percent,
                    break_even_price=result.outputs.break_even_price,
                    minimum_acceptable_price=result.outputs.minimum_acceptable_price,
                    target_price=result.outputs.target_price,
                ),
                reason_codes=list(result.reason_codes),
                fee_evidence=FeeEvidenceResponse(
                    status=profile.fee_status,
                    source=profile.fee_source,
                    effective_at=profile.fee_effective_at,
                ),
            )
            notices.extend(_result_notices(result.reason_codes))

        events = self._repository.audit_history(
            organisation_id=scope.organisation_id,
            entity_ids=[product.id, marketplace.id],
        )
        return ProductEconomicsResponse(
            scope=ScopeResponse(
                organisation_id=scope.organisation_id,
                marketplace_id=scope.marketplace_id,
            ),
            product=ProductReferenceResponse(
                product_id=product.id,
                asin=product.asin,
                title=product.title or (snapshot.title if snapshot is not None else None),
            ),
            observed_price=observed_price,
            currency_code=marketplace.default_currency_code,
            profile_source=profile_source,
            active_profile=_profile_response(profile) if profile is not None else None,
            profiles_by_scope=ProfilesByScopeResponse(
                product=(
                    _profile_response(product_profile) if product_profile is not None else None
                ),
                marketplace_default=(
                    _profile_response(marketplace_default_profile)
                    if marketplace_default_profile is not None
                    else None
                ),
            ),
            profile_history=[_profile_response(item) for item in history],
            calculation=calculation,
            notices=_deduplicate_notices(notices),
            audit_history=[
                CostProfileAuditResponse(
                    id=event.id,
                    event_type=event.event_type,
                    profile_id=str(event.event_payload.get("profile_id", "")),
                    profile_version=int(event.event_payload.get("profile_version", 0)),
                    occurred_at=event.occurred_at,
                )
                for event in events
            ],
        )


def _profile_checksum(command: CostProfileCreate, *, scope_key: str, version: int) -> str:
    payload = command.model_dump(mode="json")
    payload["profile_scope_key"] = scope_key
    payload["version"] = version
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _profile_response(profile: CostProfile) -> CostProfileResponse:
    return CostProfileResponse(
        id=profile.id,
        organisation_id=profile.organisation_id,
        marketplace_id=profile.marketplace_id,
        product_id=profile.product_id,
        scope="product" if profile.product_id is not None else "marketplace_default",
        version=profile.version,
        supersedes_profile_id=profile.supersedes_profile_id,
        currency_code=profile.currency_code,
        selling_price_tax_basis=profile.selling_price_tax_basis,
        purchase_cost=profile.supplier_unit_cost,
        gst_rate_percent=profile.gst_rate_percent,
        gst_recoverable_percent=profile.gst_recoverable_percent,
        freight_cost=profile.freight_cost,
        prep_cost=profile.prep_cost,
        packaging_cost=profile.packaging_cost,
        advertising_rate_percent=profile.advertising_rate_percent,
        returns_rate_percent=profile.returns_rate_percent,
        overhead_cost=profile.overhead_cost,
        referral_fee_rate_percent=profile.referral_fee_rate_percent,
        fulfilment_fee=profile.fulfilment_fee,
        closing_fee=profile.closing_fee,
        storage_fee=profile.storage_fee,
        fee_source=profile.fee_source,
        fee_effective_at=profile.fee_effective_at,
        fee_status=profile.fee_status,
        minimum_margin_percent=profile.minimum_margin_percent,
        target_margin_percent=profile.target_margin_percent,
        configuration_checksum=profile.configuration_checksum,
        effective_from=profile.effective_from,
        effective_to=profile.effective_to,
        created_at=profile.created_at,
    )


def _observed_price(snapshot: ProductSnapshot | None) -> ObservedPriceResponse | None:
    if (
        snapshot is None
        or snapshot.observed_on is None
        or snapshot.buy_box_price is None
        or snapshot.currency_code is None
    ):
        return None
    return ObservedPriceResponse(
        amount=snapshot.buy_box_price,
        currency_code=snapshot.currency_code,
        source_at=snapshot.snapshot_at,
        observed_on=snapshot.observed_on,
    )


def _economics_inputs(profile: CostProfile, selling_price: Decimal | None) -> EconomicsInputs:
    return EconomicsInputs(
        currency_code=profile.currency_code,
        selling_price=selling_price,
        selling_price_tax_basis=(
            profile.selling_price_tax_basis.value
            if profile.selling_price_tax_basis is not None
            else None
        ),
        purchase_cost=profile.supplier_unit_cost,
        gst_rate_percent=profile.gst_rate_percent,
        gst_recoverable_percent=profile.gst_recoverable_percent,
        freight_cost=profile.freight_cost,
        prep_cost=profile.prep_cost,
        packaging_cost=profile.packaging_cost,
        advertising_rate_percent=profile.advertising_rate_percent,
        returns_rate_percent=profile.returns_rate_percent,
        overhead_cost=profile.overhead_cost,
        referral_fee_rate_percent=profile.referral_fee_rate_percent,
        fulfilment_fee=profile.fulfilment_fee,
        closing_fee=profile.closing_fee,
        storage_fee=profile.storage_fee,
        minimum_margin_percent=profile.minimum_margin_percent,
        target_margin_percent=profile.target_margin_percent,
        fee_status=profile.fee_status.value if profile.fee_status is not None else None,
    )


def _result_notices(reason_codes: tuple[str, ...]) -> list[EconomicsNoticeResponse]:
    definitions: dict[
        str,
        tuple[
            Literal["missing", "warning"],
            str,
            Literal["observed", "calculated", "estimated", "user_confirmed"],
        ],
    ] = {
        "ECONOMICS_FEE_INPUTS_MISSING": (
            "missing",
            "One or more Amazon fee inputs are missing; fee-dependent outputs were not calculated.",
            "estimated",
        ),
        "ECONOMICS_SELLING_PRICE_TAX_BASIS_MISSING": (
            "missing",
            "The cost profile does not declare whether selling prices include tax.",
            "user_confirmed",
        ),
        "ECONOMICS_FEES_ESTIMATED": (
            "warning",
            "Amazon fees are estimates from the recorded source and effective date.",
            "estimated",
        ),
        "ECONOMICS_MARGIN_PRICE_ZERO": (
            "warning",
            "Margin is unavailable because the observed selling price is zero.",
            "calculated",
        ),
        "ECONOMICS_ROI_LANDED_COST_ZERO": (
            "warning",
            "ROI is unavailable because calculated landed cost is zero.",
            "calculated",
        ),
        "ECONOMICS_BREAK_EVEN_RATE_INVALID": (
            "warning",
            "Combined variable rates leave no valid break-even denominator.",
            "calculated",
        ),
        "ECONOMICS_MINIMUM_MARGIN_UNACHIEVABLE": (
            "warning",
            "The requested minimum margin is mathematically unreachable with these rates.",
            "calculated",
        ),
        "ECONOMICS_TARGET_MARGIN_UNACHIEVABLE": (
            "warning",
            "The target margin is mathematically unreachable with these rates.",
            "calculated",
        ),
    }
    notices: list[EconomicsNoticeResponse] = []
    for code in reason_codes:
        definition = definitions.get(code)
        if definition is None:
            continue
        severity, message, label = definition
        notices.append(
            EconomicsNoticeResponse(
                code=code,
                severity=severity,
                message=message,
                evidence_label=label,
            )
        )
    return notices


def _deduplicate_notices(
    notices: list[EconomicsNoticeResponse],
) -> list[EconomicsNoticeResponse]:
    return list({notice.code: notice for notice in notices}.values())
