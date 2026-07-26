from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import Marketplace, Organisation
from app.modules.workspaces.schemas import (
    MarketplaceResponse,
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceResponse,
)


def create_workspace(session: Session, command: WorkspaceCreate) -> WorkspaceResponse:
    organisation = Organisation(name=command.organisation_name)
    marketplace = Marketplace(
        organisation=organisation,
        code=command.marketplace_code,
        name=command.marketplace_name,
        default_currency_code=command.currency_code,
    )
    session.add(organisation)
    session.add(marketplace)
    session.commit()
    session.refresh(organisation)
    session.refresh(marketplace)
    return _to_response(organisation, [marketplace])


def list_workspaces(session: Session) -> WorkspaceListResponse:
    organisations = session.scalars(
        select(Organisation)
        .options(selectinload(Organisation.marketplaces))
        .order_by(Organisation.created_at, Organisation.id)
    ).all()
    return WorkspaceListResponse(
        items=[_to_response(item, list(item.marketplaces)) for item in organisations]
    )


def _to_response(organisation: Organisation, marketplaces: list[Marketplace]) -> WorkspaceResponse:
    return WorkspaceResponse(
        organisation_id=organisation.id,
        organisation_name=organisation.name,
        marketplaces=[MarketplaceResponse.model_validate(item) for item in marketplaces],
    )
