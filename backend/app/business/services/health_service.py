"""Estado de los componentes del sistema."""

from sqlalchemy.orm import Session

from app.data.repositories.health import HealthRepository


class HealthService:
    def __init__(self, session: Session) -> None:
        self.repo = HealthRepository(session)

    def database_available(self) -> bool:
        return self.repo.ping()
