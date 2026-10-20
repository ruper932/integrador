"""Verificación de conectividad con la base de datos."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class HealthRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ping(self) -> bool:
        try:
            self.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True
