"""Notificaciones internas del sistema (sin correo, SMS ni servicios externos)."""

from collections.abc import Iterable, Sequence

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import NotFoundError
from app.data.models.incidents import Notification
from app.data.repositories.incidents import NotificationRepository


class NotificationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = NotificationRepository(session)

    def notify(
        self, user_ids: Iterable[int], title: str, message: str, *, incident_report_id: int | None = None
    ) -> None:
        """Agrega los avisos a la transacción actual (el llamador hace commit)."""
        for user_id in dict.fromkeys(user_ids):  # sin duplicados, en orden
            self.repo.add(
                Notification(user_id=user_id, title=title, message=message, incident_report_id=incident_report_id)
            )

    def list(self, user_id: int, *, limit: int, unread_only: bool) -> tuple[Sequence[Notification], int]:
        return self.repo.list_for_user(user_id, limit=limit, unread_only=unread_only), self.repo.count_unread(user_id)

    def mark_read(self, user_id: int, notification_id: int) -> None:
        notification = self.repo.get(notification_id)
        # Una notificación ajena se trata como inexistente.
        if notification is None or notification.user_id != user_id:
            raise NotFoundError("Notificación no encontrada.")
        self.repo.mark_read(user_id, utcnow(), notification_id=notification_id)
        self.session.commit()

    def mark_all_read(self, user_id: int) -> int:
        count = self.repo.mark_read(user_id, utcnow())
        self.session.commit()
        return count
