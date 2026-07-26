from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
MarketplaceCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=32, pattern=r"^[A-Z0-9_-]+$"),
]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


class WorkspaceCreate(BaseModel):
    organisation_name: Name
    marketplace_code: MarketplaceCode
    marketplace_name: Name
    currency_code: CurrencyCode

    @field_validator("marketplace_code", "currency_code", mode="before")
    @classmethod
    def uppercase_codes(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value


class MarketplaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    default_currency_code: str


class WorkspaceResponse(BaseModel):
    organisation_id: str
    organisation_name: str
    marketplaces: list[MarketplaceResponse]


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse] = Field(default_factory=list)
