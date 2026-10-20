"""Esquemas comunes."""

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# PostgreSQL INET se lee como objeto ipaddress; se expone como texto.
IPStr = Annotated[str | None, BeforeValidator(lambda v: str(v) if v is not None else None)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    total: int
    offset: int
    limit: int


class PageParams(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)


class Message(BaseModel):
    message: str
