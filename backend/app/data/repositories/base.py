"""Repositorio genérico con operaciones comunes."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.data.database import Base


class Repository[ModelT: Base]:
    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, entity_id: int) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def get_for_update(self, entity_id: int) -> ModelT | None:
        # `of=` limita el bloqueo a la tabla principal (las relaciones se cargan con OUTER JOIN).
        stmt = (
            select(self.model)
            .where(self.model.id == entity_id)  # type: ignore[attr-defined]
            .with_for_update(of=self.model)
            .execution_options(populate_existing=True)  # relee los valores ya bloqueados
        )
        return self.session.scalars(stmt).unique().first()

    def get_by(self, **filters: Any) -> ModelT | None:
        return self.session.scalars(select(self.model).filter_by(**filters)).first()

    def list(self, *, offset: int = 0, limit: int = 100, order_by: Any = None, **filters: Any) -> Sequence[ModelT]:
        stmt = select(self.model).filter_by(**{k: v for k, v in filters.items() if v is not None})
        stmt = stmt.order_by(order_by if order_by is not None else self.model.id)  # type: ignore[attr-defined]
        return self.session.scalars(stmt.offset(offset).limit(limit)).unique().all()

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def paginate(self, stmt: Select[Any], *, offset: int, limit: int) -> tuple[Sequence[Any], int]:
        total = self.session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        items = self.session.scalars(stmt.offset(offset).limit(limit)).unique().all()
        return items, total
