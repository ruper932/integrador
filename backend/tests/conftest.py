"""Configuración de pruebas.

Las pruebas usan una base PostgreSQL exclusiva (TEST_DATABASE_URL), que se
reconstruye aplicando las migraciones Alembic al inicio de la sesión. Cada
prueba se ejecuta dentro de una transacción que se revierte al finalizar.
"""

import os
from collections.abc import Iterator
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _read_env_file() -> dict[str, str]:
    env_path = BACKEND_DIR / ".env"
    values: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


_test_url = os.environ.get("TEST_DATABASE_URL") or _read_env_file().get("TEST_DATABASE_URL")
if not _test_url:
    raise RuntimeError("Defina TEST_DATABASE_URL para ejecutar las pruebas.")
os.environ["DATABASE_URL"] = _test_url
os.environ["ENVIRONMENT"] = "test"
os.environ["TRUST_PROXY_HEADERS"] = "true"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.data.database import get_session  # noqa: E402
from app.main import app  # noqa: E402
from tests.factories import Factory  # noqa: E402


@pytest.fixture(scope="session")
def engine():  # noqa: ANN201
    engine = create_engine(_test_url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", _test_url.replace("%", "%%"))
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:  # noqa: ANN001
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def factory(db: Session) -> Factory:
    return Factory(db)


@pytest.fixture
def make_client(db: Session) -> Iterator:  # noqa: ANN201
    def override() -> Iterator[Session]:
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_session] = override
    clients: list[TestClient] = []

    def _make(ip: str = "10.0.0.10") -> TestClient:
        client = TestClient(app, headers={"X-Real-IP": ip})
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client(make_client) -> TestClient:  # noqa: ANN001
    return make_client()


@pytest.fixture
def admin_client(make_client, factory: Factory) -> TestClient:  # noqa: ANN001
    factory.user("admin", roles=["administrador"])
    return factory.login(make_client(), "admin")


@pytest.fixture
def travel(monkeypatch):  # noqa: ANN001, ANN201
    """Fija la hora actual de la aplicación (para registrar movimientos en periodos pasados)."""
    import sys
    from datetime import datetime

    from app.core import clock

    original = clock.utcnow
    modules = [m for name, m in list(sys.modules.items()) if name.startswith("app.") and m is not None]

    def _travel(moment: datetime | None) -> None:
        target = original if moment is None else (lambda: moment)
        for module in modules:
            if getattr(module, "utcnow", None) is not None and module is not clock:
                monkeypatch.setattr(module, "utcnow", target)

    return _travel
