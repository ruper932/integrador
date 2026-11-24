"""Repositorio de solicitudes de reubicación de atrapanieblas."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.data.models.relocations import RELOCATION_ACTIVE_STATUSES, FogCollectorRelocation
from app.data.repositories.base import Repository


class RelocationRepository(Repository[FogCollectorRelocation]):
    model = FogCollectorRelocation

    def search(
        self,
        *,
        offset: int,
        limit: int,
        requested_by_id: int | None = None,
        assigned_to_id: int | None = None,
        status: str | None = None,
        fog_collector_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        oldest_first: bool = False,
    ) -> tuple[Sequence[FogCollectorRelocation], int]:
        model = FogCollectorRelocation
        filters: list[Any] = []
        for column, value in (
            (model.requested_by_id, requested_by_id),
            (model.assigned_to_id, assigned_to_id),
            (model.status, status),
            (model.fog_collector_id, fog_collector_id),
        ):
            if value is not None:
                filters.append(column == value)
        if date_from:
            filters.append(model.created_at >= date_from)
        if date_to:
            filters.append(model.created_at <= date_to)
        # La bandeja de atención muestra primero lo más antiguo; el resto, lo más reciente.
        order = (model.created_at, model.id) if oldest_first else (model.created_at.desc(), model.id.desc())
        return self.paginate(select(model).where(*filters).order_by(*order), offset=offset, limit=limit)

    def active_for(self, fog_collector_id: int) -> FogCollectorRelocation | None:
        stmt = select(FogCollectorRelocation).where(
            FogCollectorRelocation.fog_collector_id == fog_collector_id,
            FogCollectorRelocation.status.in_(RELOCATION_ACTIVE_STATUSES),
        )
        return self.session.scalars(stmt).unique().first()

    def active_fog_collector_ids(self) -> set[int]:
        stmt = select(FogCollectorRelocation.fog_collector_id).where(
            FogCollectorRelocation.status.in_(RELOCATION_ACTIVE_STATUSES)
        )
        return set(self.session.scalars(stmt).all())

    def count_by_status(
        self, *, requested_by_id: int | None = None, assigned_to_id: int | None = None
    ) -> dict[str, int]:
        stmt = select(FogCollectorRelocation.status, func.count(FogCollectorRelocation.id)).group_by(
            FogCollectorRelocation.status
        )
        if requested_by_id is not None:
            stmt = stmt.where(FogCollectorRelocation.requested_by_id == requested_by_id)
        if assigned_to_id is not None:
            stmt = stmt.where(FogCollectorRelocation.assigned_to_id == assigned_to_id)
        return {row[0]: row[1] for row in self.session.execute(stmt).all()}
