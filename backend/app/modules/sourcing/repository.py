from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.models.domain import (
    Marketplace,
    Product,
    ProductSnapshot,
    ScoreResult,
    Supplier,
    SupplierOffer,
)


@dataclass(frozen=True, slots=True)
class SupplierOfferPage:
    items: list[SupplierOffer]
    total_items: int


class SourcingRepository:
    """Bounded sourcing persistence with explicit tenant and marketplace predicates."""

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

    def find_or_create_supplier(self, organisation_id: str, name: str) -> Supplier:
        supplier = self.session.scalar(
            select(Supplier).where(
                Supplier.organisation_id == organisation_id,
                func.lower(Supplier.name) == name.lower(),
            )
        )
        if supplier is None:
            supplier = Supplier(id=str(uuid.uuid4()), organisation_id=organisation_id, name=name)
            self.session.add(supplier)
        return supplier

    def list_offers(
        self,
        *,
        organisation_id: str,
        marketplace_id: str,
        product_id: str,
        page: int,
        page_size: int,
    ) -> SupplierOfferPage:
        predicate = (
            SupplierOffer.organisation_id == organisation_id,
            SupplierOffer.marketplace_id == marketplace_id,
            SupplierOffer.product_id == product_id,
        )
        total_items = int(
            self.session.scalar(select(func.count(SupplierOffer.id)).where(*predicate)) or 0
        )
        items = list(
            self.session.scalars(
                select(SupplierOffer)
                .where(*predicate)
                .options(
                    selectinload(SupplierOffer.supplier),
                    selectinload(SupplierOffer.price_tiers),
                )
                .order_by(SupplierOffer.quotation_date.desc(), SupplierOffer.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return SupplierOfferPage(items=items, total_items=total_items)

    def get_offer(
        self,
        *,
        organisation_id: str,
        marketplace_id: str,
        product_id: str,
        offer_id: str,
    ) -> SupplierOffer:
        offer = self.session.scalar(
            select(SupplierOffer)
            .where(
                SupplierOffer.id == offer_id,
                SupplierOffer.organisation_id == organisation_id,
                SupplierOffer.marketplace_id == marketplace_id,
                SupplierOffer.product_id == product_id,
            )
            .options(
                selectinload(SupplierOffer.supplier),
                selectinload(SupplierOffer.price_tiers),
            )
        )
        if offer is None:
            raise NotFoundError("Supplier offer")
        return offer

    def latest_snapshot(self, product: Product) -> ProductSnapshot | None:
        if product.latest_snapshot_id is None:
            return None
        return self.session.scalar(
            select(ProductSnapshot).where(
                ProductSnapshot.id == product.latest_snapshot_id,
                ProductSnapshot.product_id == product.id,
            )
        )

    def latest_confidence_score(self, snapshot_id: str | None) -> ScoreResult | None:
        if snapshot_id is None:
            return None
        return self.session.scalar(
            select(ScoreResult)
            .where(
                ScoreResult.snapshot_id == snapshot_id,
                ScoreResult.score_name == "data_confidence",
            )
            .order_by(
                ScoreResult.created_at.desc(),
                ScoreResult.formula_version.desc(),
                ScoreResult.id.desc(),
            )
            .limit(1)
        )
