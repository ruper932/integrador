"""Perfil propio: el usuario autenticado revisa y actualiza sus datos."""

from sqlalchemy import select

from app.data.models.security import AuditLog
from tests.factories import DEFAULT_PASSWORD

ME = "/api/v1/auth/me"
MY_PROFILE = "/api/v1/auth/me/profile"


def payload(**overrides):
    profile = {
        "first_names": "rosa  elena",
        "paternal_surname": "QUISPE",
        "maternal_surname": None,
        "ci_number": "4455667",
        "ci_complement": None,
        "ci_issued_in": "LP",
        "institutional_email": None,
        "personal_email": "Rosa@Example.com",
        "mobile_phone": "76543210",
        "birth_date": "1992-07-03",
        "address": "Titicachi",
    }
    profile.update(overrides)
    return {"profile": profile, "degrees": []}


def test_user_sees_and_updates_own_profile(make_client, factory, db):
    client = factory.client_for(make_client(), "rosa", ["docente"])
    me = client.get(ME).json()
    assert me["profile"]["first_names"] == "Usuario"

    levels = {x["code"]: x["id"] for x in client.get("/api/v1/catalogs/academic-levels").json()}
    institutions = {x["acronym"]: x["id"] for x in client.get("/api/v1/catalogs/institutions").json()}
    body = payload()
    body["degrees"] = [
        {
            "academic_level_id": levels["tecnico_superior"],
            "title": "Técnico Superior en Agropecuaria",
            "institution_id": institutions["UPEA"],
            "graduation_year": 2019,
        }
    ]
    response = client.put(MY_PROFILE, json=body)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["full_name"] == "Rosa Elena Quispe"
    assert updated["profile"]["personal_email"] == "rosa@example.com"
    assert updated["degrees"][0]["institution"]["acronym"] == "UPEA"
    assert updated["permissions"]  # sigue siendo la respuesta de /auth/me

    log = db.scalars(select(AuditLog).where(AuditLog.action == "perfil.actualizar_propio")).one()
    assert "mobile_phone" in log.details["perfil"]
    assert "76543210" not in str(log.details)


def test_user_cannot_change_own_position_or_roles(admin_client, make_client, factory):
    user = factory.user("pedro", roles=["docente"])
    positions = {p["code"]: p["id"] for p in admin_client.get("/api/v1/catalogs/positions").json()}
    client = factory.login(make_client(), "pedro")
    body = payload(ci_number="7788990")
    body["profile"]["position_id"] = positions["director"]
    body["role_ids"] = [1]
    response = client.put(MY_PROFILE, json=body)
    assert response.status_code == 200
    me = response.json()
    assert me["profile"]["position"] is None
    assert [r["name"] for r in me["roles"]] == ["docente"]
    assert admin_client.get(f"/api/v1/users/{user.id}").json()["profile"]["position"] is None


def test_own_profile_validations(make_client, factory):
    client = factory.client_for(make_client(), "lucia", ["docente"])
    assert client.put(MY_PROFILE, json=payload(mobile_phone="44556677")).status_code == 422
    assert client.put(MY_PROFILE, json=payload(ci_number="ABC")).status_code == 422
    assert client.put(MY_PROFILE, json=payload(paternal_surname=None)).status_code == 422
    assert client.put(MY_PROFILE, json=payload(personal_email="sin-arroba")).status_code == 422


def test_own_profile_cannot_take_another_users_ci(make_client, factory):
    factory.client_for(make_client(), "uno", ["docente"]).put(MY_PROFILE, json=payload(ci_number="3333333"))
    other = factory.client_for(make_client(), "dos", ["docente"])
    response = other.put(MY_PROFILE, json=payload(ci_number="3333333"))
    assert response.json()["error"]["code"] == "ci_duplicado"


def test_profile_requires_session_and_changed_password(make_client, factory):
    assert make_client().put(MY_PROFILE, json=payload()).status_code == 401
    factory.user("nuevo", roles=["docente"], must_change_password=True)
    client = factory.login(make_client(), "nuevo")
    blocked = client.put(MY_PROFILE, json=payload(ci_number="1212121"))
    assert blocked.json()["error"]["code"] == "cambio_contrasena_requerido"


def test_change_password_from_profile_keeps_current_session(make_client, factory):
    client = factory.client_for(make_client(), "marta", ["docente"])
    other_device = factory.login(make_client(), "marta")
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "OtraClave-2026"},
    )
    assert response.status_code == 200
    assert client.get(ME).status_code == 200
    assert other_device.get(ME).status_code == 401
