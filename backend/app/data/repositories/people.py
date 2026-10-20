"""Repositorios de perfiles de usuario y catálogos de formación."""

from sqlalchemy import func, select

from app.data.models.people import AcademicLevel, Institution, Position, UserProfile
from app.data.repositories.base import Repository


class UserProfileRepository(Repository[UserProfile]):
    model = UserProfile

    def get(self, entity_id: int) -> UserProfile | None:
        return self.session.get(UserProfile, entity_id)

    def find_by_ci(self, ci_number: str, ci_complement: str | None) -> UserProfile | None:
        stmt = select(UserProfile).where(
            UserProfile.ci_number == ci_number,
            func.coalesce(UserProfile.ci_complement, "") == (ci_complement or ""),
        )
        return self.session.scalars(stmt).first()

    def find_by_institutional_email(self, email: str) -> UserProfile | None:
        stmt = select(UserProfile).where(func.lower(UserProfile.institutional_email) == email.lower())
        return self.session.scalars(stmt).first()


class AcademicLevelRepository(Repository[AcademicLevel]):
    model = AcademicLevel


class InstitutionRepository(Repository[Institution]):
    model = Institution

    def get_by_name(self, name: str) -> Institution | None:
        return self.session.scalars(select(Institution).where(func.lower(Institution.name) == name.lower())).first()


class PositionRepository(Repository[Position]):
    model = Position
