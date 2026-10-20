"""Utilidades para crear datos de prueba."""

import itertools

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.data.models.people import UserProfile
from app.data.models.security import Role, User

DEFAULT_PASSWORD = "Clave-Segura-2024"
_ci = itertools.count(1_000_000)


class Factory:
    def __init__(self, session: Session) -> None:
        self.session = session

    def role(self, name: str) -> Role:
        role = self.session.scalars(select(Role).where(Role.name == name)).one()
        return role

    def user(
        self,
        username: str,
        *,
        roles: list[str],
        password: str = DEFAULT_PASSWORD,
        must_change_password: bool = False,
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username,
            profile=UserProfile(
                first_names="Usuario",
                paternal_surname=username.capitalize(),
                ci_number=str(next(_ci)),
                mobile_phone="71234567",
            ),
            password_hash=hash_password(password),
            is_active=is_active,
            must_change_password=must_change_password,
            failed_login_attempts=0,
            roles=[self.role(r) for r in roles],
        )
        self.session.add(user)
        self.session.commit()
        return user

    def login(self, client: TestClient, username: str, password: str = DEFAULT_PASSWORD) -> TestClient:
        response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.text
        return client

    def client_for(self, client: TestClient, username: str, roles: list[str]) -> TestClient:
        self.user(username, roles=roles)
        return self.login(client, username)
