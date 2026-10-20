"""Datos personales y formación académica de los usuarios (modelo normalizado)."""

import itertools
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.data.models.security import AuditLog

_ci = itertools.count(8_000_000)


def ids(client, path, key="code"):
    return {x[key]: x["id"] for x in client.get(f"/api/v1/catalogs/{path}").json()}


def new_user(admin_client, username="docente2", degrees=None, **profile_overrides):
    roles = {r["name"]: r["id"] for r in admin_client.get("/api/v1/roles").json()}
    levels = ids(admin_client, "academic-levels")
    institutions = ids(admin_client, "institutions", key="acronym")
    positions = ids(admin_client, "positions")
    profile = {
        "first_names": "maría  del carmen",
        "paternal_surname": "CHOQUE",
        "maternal_surname": "apaza",
        "ci_number": str(next(_ci)),
        "ci_complement": "1a",
        "ci_issued_in": "LP",
        "institutional_email": "MCHOQUE@cea-ildefonso.edu.bo",
        "personal_email": "maria@example.com",
        "mobile_phone": "73456789",
        "birth_date": "1985-05-20",
        "address": "Comunidad Titicachi, Chuma, provincia Muñecas",
        "position_id": positions["docente"],
    }
    profile.update(profile_overrides)
    return admin_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "role_ids": [roles["director"]],
            "profile": profile,
            "degrees": degrees
            if degrees is not None
            else [
                {
                    "academic_level_id": levels["maestro_normalista"],
                    "title": "Maestro en Educación Primaria Comunitaria Vocacional",
                    "institution_id": institutions["ESFM Warisata"],
                    "graduation_year": 2015,
                },
                {
                    "academic_level_id": levels["licenciatura"],
                    "title": "Licenciatura en Ciencias de la Educación",
                    "institution_id": institutions["UMSA"],
                },
            ],
        },
    )


def test_catalogs_are_seeded(admin_client):
    levels = ids(admin_client, "academic-levels")
    assert {"bachiller", "tecnico_superior", "maestro_normalista", "licenciatura", "maestria"} <= set(levels)
    names = {i["name"] for i in admin_client.get("/api/v1/catalogs/institutions").json()}
    assert "Universidad Mayor de San Andrés" in names
    assert {"director", "docente"} <= set(ids(admin_client, "positions"))


def test_create_user_with_full_profile_and_degrees(admin_client):
    response = new_user(admin_client)
    assert response.status_code == 201, response.text
    user = response.json()["user"]
    p = user["profile"]
    # Los datos se normalizan antes de guardarse.
    assert p["first_names"] == "María Del Carmen"
    assert p["paternal_surname"] == "Choque"
    assert p["ci_complement"] == "1A"
    assert p["institutional_email"] == "mchoque@cea-ildefonso.edu.bo"
    assert p["position"]["code"] == "docente"
    assert user["full_name"] == "María Del Carmen Choque Apaza"
    assert user["profile_complete"] is True
    assert [d["institution"]["acronym"] for d in user["degrees"]] == ["ESFM Warisata", "UMSA"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ci_number", "12AB"),
        ("mobile_phone", "22445566"),  # fijo, no celular
        ("mobile_phone", "7123456"),  # 7 dígitos
        ("ci_issued_in", "XX"),
        ("institutional_email", "sin-arroba"),
        ("first_names", "Juan123"),
    ],
)
def test_invalid_profile_fields(admin_client, field, value):
    assert new_user(admin_client, **{field: value}).status_code == 422


def test_at_least_one_surname_is_required(admin_client):
    response = new_user(admin_client, paternal_surname=None, maternal_surname=None)
    assert response.status_code == 422


def test_ci_and_institutional_email_are_unique(admin_client):
    first = new_user(admin_client, username="uno").json()["user"]["profile"]
    dup_ci = new_user(
        admin_client,
        username="dos",
        ci_number=first["ci_number"],
        ci_complement="1A",
        institutional_email="otro@cea.edu.bo",
    )
    assert dup_ci.json()["error"]["code"] == "ci_duplicado"
    dup_mail = new_user(admin_client, username="tres", institutional_email="MChoque@cea-ildefonso.edu.bo")
    assert dup_mail.json()["error"]["code"] == "correo_duplicado"
    # Mismo número con otro complemento: son personas distintas.
    other = new_user(
        admin_client,
        username="cuatro",
        ci_number=first["ci_number"],
        ci_complement="2B",
        institutional_email=None,
    )
    assert other.status_code == 201


def test_update_profile_and_degrees_audits_only_field_names(admin_client, db):
    user = new_user(admin_client).json()["user"]
    profile = {**user["profile"], "position_id": None, "mobile_phone": "69876543", "address": "Chuma"}
    profile.pop("position")
    response = admin_client.put(f"/api/v1/users/{user['id']}", json={"profile": profile, "degrees": []})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile"]["mobile_phone"] == "69876543"
    assert body["degrees"] == []
    log = db.scalars(select(AuditLog).where(AuditLog.action == "usuario.actualizar")).all()[-1]
    assert "mobile_phone" in log.details["perfil"]
    assert "69876543" not in str(log.details)


def test_unknown_institution_is_rejected(admin_client):
    roles = {r["name"]: r["id"] for r in admin_client.get("/api/v1/roles").json()}
    levels = ids(admin_client, "academic-levels")
    response = admin_client.post(
        "/api/v1/users",
        json={
            "username": "x-inst",
            "role_ids": [roles["docente"]],
            "profile": {
                "first_names": "Ana",
                "paternal_surname": "Ticona",
                "ci_number": str(next(_ci)),
                "mobile_phone": "61234567",
                "birth_date": "1990-02-11",
            },
            "degrees": [{"academic_level_id": levels["licenciatura"], "title": "Agronomía", "institution_id": 99999}],
        },
    )
    assert response.json()["error"]["code"] == "institucion_invalida"


def test_admin_adds_institution_and_others_cannot(admin_client, make_client, factory):
    created = admin_client.post(
        "/api/v1/catalogs/institutions",
        json={"name": "Instituto Tecnológico de Prueba", "institution_type": "instituto_tecnico", "city": "Chuma"},
    )
    assert created.status_code == 201
    again = admin_client.post(
        "/api/v1/catalogs/institutions",
        json={"name": "instituto  tecnológico de prueba", "institution_type": "instituto_tecnico"},
    )
    assert again.status_code == 409
    director = factory.client_for(make_client(), "dir-cat", ["director"])
    assert director.get("/api/v1/catalogs/institutions").status_code == 200
    forbidden = director.post("/api/v1/catalogs/institutions", json={"name": "Otra", "institution_type": "otra"})
    assert forbidden.status_code == 403


def test_search_users_by_surname_and_ci(admin_client):
    user = new_user(admin_client).json()["user"]
    by_name = admin_client.get("/api/v1/users", params={"q": "choque"}).json()
    assert [u["username"] for u in by_name["items"]] == ["docente2"]
    by_ci = admin_client.get("/api/v1/users", params={"q": user["profile"]["ci_number"]}).json()
    assert by_ci["total"] == 1


def years_ago(years: int, days: int = 0) -> str:
    today = date.today()
    return (today.replace(year=today.year - years) + timedelta(days=days)).isoformat()


def test_birth_date_is_required_and_person_must_be_adult(admin_client):
    missing = new_user(admin_client, "sin-fecha", birth_date=None)
    assert missing.status_code == 422

    minor = new_user(admin_client, "menor", birth_date=years_ago(18, days=1))
    assert minor.status_code == 422
    assert minor.json()["error"]["code"] == "menor_de_edad"
    future = new_user(admin_client, "futuro", birth_date=years_ago(-1))
    assert future.json()["error"]["code"] == "fecha_nacimiento_invalida"
    too_old = new_user(admin_client, "anciano", birth_date="1910-01-01")
    assert too_old.json()["error"]["code"] == "fecha_nacimiento_invalida"

    adult = new_user(admin_client, "adulto", degrees=[], birth_date=years_ago(18))
    assert adult.status_code == 201, adult.text
    assert adult.json()["user"]["profile"]["birth_date"] == years_ago(18)


def test_graduation_year_must_fit_the_age_for_the_level(admin_client):
    levels = ids(admin_client, "academic-levels")
    institutions = ids(admin_client, "institutions", key="acronym")
    birth_year = date.today().year - 20
    user = new_user(admin_client, "joven", degrees=[], birth_date=f"{birth_year}-03-01").json()["user"]

    def save(level: str, year: int):
        return admin_client.put(
            f"/api/v1/users/{user['id']}",
            json={
                "degrees": [
                    {
                        "academic_level_id": levels[level],
                        "title": "Título de prueba",
                        "institution_id": institutions["UMSA"],
                        "graduation_year": year,
                    }
                ]
            },
        )

    # 20 años: una licenciatura (edad mínima 21) es imposible; el bachillerato a los 17, posible.
    bad = save("licenciatura", birth_year + 19)
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "egreso_incoherente"
    assert bad.json()["error"]["details"]["anio_minimo"] == birth_year + 21
    assert save("bachiller", birth_year + 17).status_code == 200


def test_changing_birth_date_revalidates_existing_degrees(admin_client):
    created = new_user(admin_client, "cambia-fecha").json()["user"]  # normalista egresado en 2015
    profile = {**created["profile"], "position_id": None}
    profile.pop("position")
    # Nacida en 2000: en 2015 tenía 15 años, no pudo egresar como maestra normalista.
    response = admin_client.put(
        f"/api/v1/users/{created['id']}", json={"profile": {**profile, "birth_date": "2000-01-01"}}
    )
    assert response.json()["error"]["code"] == "egreso_incoherente"
    assert admin_client.get(f"/api/v1/users/{created['id']}").json()["profile"]["birth_date"] == "1985-05-20"


def test_academic_levels_expose_min_graduation_age(admin_client):
    levels = {x["code"]: x for x in admin_client.get("/api/v1/catalogs/academic-levels").json()}
    assert levels["licenciatura"]["min_graduation_age"] == 21
    assert levels["bachiller"]["min_graduation_age"] == 16
