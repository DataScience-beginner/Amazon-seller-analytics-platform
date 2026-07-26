from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.domain import AuditEvent, CostProfile, Marketplace, Product, ProductSnapshot


class EconomicsRepository:
    """Tenant- and marketplace-scoped persistence boundary for Phase 2 economics."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_scope(self, organisation_id: str, marketplace_id: str) -> Marketplace:
        marketplace = self.session.scalar(
            select(Marketplace).where(
                Marketplace.id == marketplace_id,
                Marketplace.organisation_id == organisation_id,
            )
        )
        if marketplace is None:
            raise NotFoundError("Marketplace")
        return marketplace

    def get_product(self, organisation_id: str, marketplace_id: str, product_id: str) -> Product:
        product = self.session.scalar(
            select(Product).where(
                Product.id == product_id,
                Product.organisation_id == organisation_id,
                Product.marketplace_id == marketplace_id,
            )
        )
        if product is None:
            raise NotFoundError("Product")
        return product

    def get_latest_snapshot(self, product: Product) -> ProductSnapshot | None:
        if product.latest_snapshot_id is None:
            return None
        return self.session.scalar(
            select(ProductSnapshot).where(
                ProductSnapshot.id == product.latest_snapshot_id,
                ProductSnapshot.product_id == product.id,
            )
        )

    def resolve_profile(
        self,
        *,
        organisation_id: str,
        marketplace_id: str,
        product_id: str,
        as_of: datetime,
    ) -> tuple[CostProfile | None, Literal["product", "marketplace_default"] | None]:
        product_profile, marketplace_profile = self.resolve_profiles_by_scope(
            organisation_id=organisation_id,
            marketplace_id=marketplace_id,
            product_id=product_id,
            as_of=as_of,
        )
        if product_profile is not None:
            return product_profile, "product"
        if marketplace_profile is not None:
            return marketplace_profile, "marketplace_default"
        return None, None

    def resolve_profiles_by_scope(
        self,
        *,
        organisation_id: str,
        marketplace_id: str,
        product_id: str,
        as_of: datetime,
    ) -> tuple[CostProfile | None, CostProfile | None]:
        return (
            self._resolve_profile_scope(
                organisation_id=organisation_id,
                marketplace_id=marketplace_id,
                scope_key=product_id,
                as_of=as_of,
            ),
            self._resolve_profile_scope(
                organisation_id=organisation_id,
                marketplace_id=marketplace_id,
                scope_key="marketplace_default",
                as_of=as_of,
            ),
        )

    def _resolve_profile_scope(
        self,
        *,
        organisation_id: str,
        marketplace_id: str,
        scope_key: str,
        as_of: datetime,
    ) -> CostProfile | None:
        return self.session.scalar(
            select(CostProfile)
            .where(
                CostProfile.organisation_id == organisation_id,
                CostProfile.marketplace_id == marketplace_id,
                CostProfile.profile_scope_key == scope_key,
                CostProfile.effective_from <= as_of,
                or_(CostProfile.effective_to.is_(None), CostProfile.effective_to > as_of),
            )
            .order_by(CostProfile.effective_from.desc(), CostProfile.version.desc())
            .limit(1)
        )

    def profile_history(
        self,
        *,
        organisation_id: str,
        marketplace_id: str,
        product_id: str,
        limit: int = 50,
    ) -> list[CostProfile]:
        return list(
            self.session.scalars(
                select(CostProfile)
                .where(
                    CostProfile.organisation_id == organisation_id,
                    CostProfile.marketplace_id == marketplace_id,
                    CostProfile.profile_scope_key.in_([product_id, "marketplace_default"]),
                )
                .order_by(CostProfile.effective_from.desc(), CostProfile.version.desc())
                .limit(limit)
            ).all()
        )

    def current_revision(
        self, organisation_id: str, marketplace_id: str, scope_key: str
    ) -> CostProfile | None:
        return self.session.scalar(
            select(CostProfile)
            .where(
                CostProfile.organisation_id == organisation_id,
                CostProfile.marketplace_id == marketplace_id,
                CostProfile.profile_scope_key == scope_key,
                CostProfile.effective_to.is_(None),
            )
            .order_by(CostProfile.version.desc())
            .with_for_update()
            .limit(1)
        )

    def audit_history(
        self,
        *,
        organisation_id: str,
        entity_ids: list[str],
        limit: int = 50,
    ) -> list[AuditEvent]:
        return list(
            self.session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.organisation_id == organisation_id,
                    AuditEvent.entity_type == "cost_profile_scope",
                    AuditEvent.entity_id.in_(entity_ids),
                )
                .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
                .limit(limit)
            ).all()
        )
