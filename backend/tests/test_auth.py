from sqlalchemy import select

from app.data.models.security import AuditLog, User
from tests.factories import DEFAULT_PASSWORD

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/health/db").json()["status"] == "ok"


def test_login_sets_httponly_cookie_and_returns_permissions(client, factory):
    factory.user("ana", roles=["docente"])
    response = client.post(LOGIN, json={"username": "ana", "password": DEFAULT_PASSWORD})
    assert response.status_code == 200
    cookie_header = response.headers["set-cookie"]
    assert "HttpOnly" in cookie_header
    assert "samesite=strict" in cookie_header.lower()
    assert "access_token" not in response.json()

    me = client.get(ME).json()
    assert me["username"] == "ana"
    assert set(me["permissions"]) == {
        "dashboard.consultar",
        "mediciones.consultar",
        "reportes.consultar",
        "infraestructura.consultar",
        "incidencias.reportar",
    }


def test_password_is_stored_hashed(factory, db):
    user = factory.user("hash", roles=["docente"])
    stored = db.get(User, user.id).password_hash
    assert DEFAULT_PASSWORD not in stored
    assert stored.startswith("scrypt$")


def test_invalid_credentials_have_same_message_for_unknown_user(client, factory):
    factory.user("beto", roles=["docente"])
    wrong = client.post(LOGIN, json={"username": "beto", "password": "incorrecta-123"})
    unknown = client.post(LOGIN, json={"username": "nadie", "password": "incorrecta-123"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_failed_login_audit_never_contains_password(client, factory, db):
    factory.user("carla", roles=["docente"])
    client.post(LOGIN, json={"username": "carla", "password": "secreto-que-no-debe-verse-1"})
    logs = db.scalars(select(AuditLog).where(AuditLog.action == "auth.login_fallido")).all()
    assert logs
    assert all("secreto-que-no-debe-verse-1" not in str(log.details) for log in logs)


def test_account_locks_after_repeated_failures(client, factory):
    factory.user("dario", roles=["docente"])
    for _ in range(5):
        client.post(LOGIN, json={"username": "dario", "password": "mala-clave-1"})
    response = client.post(LOGIN, json={"username": "dario", "password": DEFAULT_PASSWORD})
    assert response.status_code == 401


def test_inactive_user_cannot_login(client, factory):
    factory.user("eva", roles=["docente"], is_active=False)
    assert client.post(LOGIN, json={"username": "eva", "password": DEFAULT_PASSWORD}).status_code == 401


def test_unauthenticated_request_returns_401(client):
    response = client.get(ME)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "no_autenticado"


def test_logout_invalidates_session(client, factory):
    factory.client_for(client, "fabio", ["docente"])
    token = client.cookies.get("atrapanieblas_session")
    assert client.post("/api/v1/auth/logout").status_code == 200
    # Aunque se reutilice el token anterior, la sesión ya está revocada.
    client.cookies.set("atrapanieblas_session", token, path="/api")
    assert client.get(ME).status_code == 401


def test_temporary_password_forces_change_before_other_operations(make_client, factory):
    factory.user("gina", roles=["director"], must_change_password=True)
    first = factory.login(make_client(), "gina")
    second = factory.login(make_client(), "gina")

    blocked = first.get("/api/v1/dashboard/summary")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "cambio_contrasena_requerido"
    assert first.get(ME).status_code == 200

    weak = first.post(
        "/api/v1/auth/change-password", json={"current_password": DEFAULT_PASSWORD, "new_password": "corta"}
    )
    assert weak.status_code == 422

    changed = first.post(
        "/api/v1/auth/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "NuevaClave-2025"},
    )
    assert changed.status_code == 200
    assert first.get("/api/v1/dashboard/summary").status_code == 200
    # Las demás sesiones se invalidan tras el cambio de contraseña.
    assert second.get(ME).status_code == 401
