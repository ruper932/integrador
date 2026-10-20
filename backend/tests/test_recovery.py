from sqlalchemy import select

from app.data.models.security import AccountRecoveryRequest
from tests.factories import DEFAULT_PASSWORD

SUBMIT = "/api/v1/auth/recovery-requests"
ADMIN = "/api/v1/admin/recovery-requests"


def test_public_request_does_not_reveal_if_user_exists(make_client, factory):
    factory.user("real", roles=["docente"])
    existing = make_client("10.0.0.1").post(SUBMIT, json={"username": "real"})
    missing = make_client("10.0.0.2").post(SUBMIT, json={"username": "fantasma"})
    assert existing.status_code == missing.status_code == 202
    assert existing.json() == missing.json()


def test_rate_limit_per_ip(make_client):
    client = make_client("10.9.9.9")
    for i in range(5):
        assert client.post(SUBMIT, json={"username": f"u{i}"}).status_code == 202
    assert client.post(SUBMIT, json={"username": "otro"}).status_code == 429


def test_rate_limit_per_username_is_silent(make_client, factory, db):
    factory.user("insistente", roles=["docente"])
    for i in range(5):
        response = make_client(f"10.1.1.{i}").post(SUBMIT, json={"username": "insistente"})
        assert response.status_code == 202
    count = len(
        db.scalars(
            select(AccountRecoveryRequest).where(AccountRecoveryRequest.username_requested == "insistente")
        ).all()
    )
    assert count == 3


def test_full_recovery_flow(admin_client, make_client, factory):
    factory.user("perdido", roles=["docente"])
    old_session = factory.login(make_client(), "perdido")
    make_client("10.2.2.2").post(SUBMIT, json={"username": "perdido", "message": "Olvidé mi clave"})

    # Una solicitud pendiente no da acceso: la contraseña sigue siendo la anterior.
    assert old_session.get("/api/v1/auth/me").status_code == 200
    pending = admin_client.get(ADMIN, params={"status": "pendiente"}).json()["items"]
    request = next(r for r in pending if r["username_requested"] == "perdido")

    not_verified = admin_client.post(
        f"{ADMIN}/{request['id']}/approve", json={"identity_verified": False, "verification_note": "sin carnet"}
    )
    assert not_verified.json()["error"]["code"] == "identidad_no_verificada"

    approved = admin_client.post(
        f"{ADMIN}/{request['id']}/approve",
        json={"identity_verified": True, "verification_note": "Carnet de identidad presentado"},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["request"]["status"] == "aprobada"
    temporary = body["temporary_password"]
    assert temporary

    # El restablecimiento invalida las sesiones activas.
    assert old_session.get("/api/v1/auth/me").status_code == 401
    fresh = make_client()
    assert (
        fresh.post("/api/v1/auth/login", json={"username": "perdido", "password": DEFAULT_PASSWORD}).status_code == 401
    )
    login = fresh.post("/api/v1/auth/login", json={"username": "perdido", "password": temporary})
    assert login.json()["user"]["must_change_password"] is True

    again = admin_client.post(f"{ADMIN}/{request['id']}/reject", json={"reason": "duplicado"})
    assert again.json()["error"]["code"] == "solicitud_resuelta"

    audit = admin_client.get("/api/v1/admin/audit-logs", params={"action": "recuperacion.aprobar"}).json()
    assert audit["total"] == 1


def test_reject_request_for_unknown_user(admin_client, make_client):
    make_client("10.3.3.3").post(SUBMIT, json={"username": "desconocido"})
    request = admin_client.get(ADMIN).json()["items"][0]
    assert request["user_id"] is None
    approve = admin_client.post(
        f"{ADMIN}/{request['id']}/approve", json={"identity_verified": True, "verification_note": "verificado"}
    )
    assert approve.json()["error"]["code"] == "usuario_inexistente"
    rejected = admin_client.post(f"{ADMIN}/{request['id']}/reject", json={"reason": "No es usuario del sistema"})
    assert rejected.json()["status"] == "rechazada"


def test_only_admin_can_resolve(make_client, factory):
    director = factory.client_for(make_client(), "director", ["director"])
    assert director.get(ADMIN).status_code == 403
    assert director.post(f"{ADMIN}/1/reject", json={"reason": "no autorizado"}).status_code == 403
