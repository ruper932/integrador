"""Reubicación de atrapanieblas: docente solicita → mantenimiento acepta, inicia y finaliza (o rechaza)."""

import pytest
from sqlalchemy import select

from app.data.models.iot import DeviceLocation
from app.data.models.security import AuditLog

RELOCATIONS = "/api/v1/relocations"


@pytest.fixture
def site(admin_client):
    def location(name):
        response = admin_client.post("/api/v1/locations", json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()

    origin, patio, huerto = location("Ladera norte"), location("Patio trasero"), location("Huerto escolar")
    fc = admin_client.post(
        "/api/v1/fog-collectors",
        json={"code": "AN-10", "name": "Atrapanieblas norte", "location_id": origin["id"], "orientation": "NE"},
    ).json()
    device = admin_client.post(
        "/api/v1/devices", json={"code": "esp32-30", "name": "Estación norte", "fog_collector_id": fc["id"]}
    ).json()["device"]
    return {"fc": fc, "origin": origin, "patio": patio, "huerto": huerto, "device": device}


@pytest.fixture
def people(make_client, factory, admin_client):
    return {
        "docente": factory.client_for(make_client(), "docente1", ["docente"]),
        "docente2": factory.client_for(make_client(), "docente2", ["docente"]),
        "director": factory.client_for(make_client(), "directora", ["director"]),
        "tecnico": factory.client_for(make_client(), "tecnico1", ["mantenimiento"]),
        "tecnico2": factory.client_for(make_client(), "tecnico2", ["mantenimiento"]),
        "admin": admin_client,
    }


def request(client, site, **overrides):
    payload = {
        "fog_collector_id": site["fc"]["id"],
        "reason": "espacio_insuficiente",
        "description": "Se construirá un aula nueva donde está instalado el atrapanieblas.",
        "proposed_location_id": site["patio"]["id"],
    } | overrides
    return client.post(RELOCATIONS, json=payload)


def created(client, site, **overrides):
    response = request(client, site, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


def finish_payload(site, **overrides):
    return {
        "destination_location_id": site["patio"]["id"],
        "new_orientation": "N",
        "work_notes": "Se desmontó la malla, se trasladaron los postes y se ancló en el patio.",
    } | overrides


def test_full_flow_moves_fog_collector_and_its_station(people, site, db):
    r = created(people["docente"], site)
    assert r["status"] == "pendiente"
    assert r["origin_location"]["name"] == "Ladera norte"
    assert r["proposed_location"]["name"] == "Patio trasero"

    alert = people["tecnico"].get("/api/v1/notifications").json()
    assert alert["unread"] == 1 and alert["items"][0]["relocation_id"] == r["id"]
    open_ids = [x["id"] for x in people["tecnico"].get(RELOCATIONS, params={"scope": "open"}).json()["items"]]
    assert open_ids == [r["id"]]

    tecnico = people["tecnico"]
    assert tecnico.post(f"{RELOCATIONS}/{r['id']}/accept").json()["status"] == "aceptado"
    # Otro técnico no puede aceptarla de nuevo ni avanzar una solicitud ajena.
    assert people["tecnico2"].post(f"{RELOCATIONS}/{r['id']}/accept").status_code == 409
    assert people["tecnico2"].post(f"{RELOCATIONS}/{r['id']}/start").status_code == 403
    assert tecnico.post(f"{RELOCATIONS}/{r['id']}/start").json()["status"] == "en_progreso"

    done = tecnico.post(f"{RELOCATIONS}/{r['id']}/finish", json=finish_payload(site))
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "finalizado"
    assert body["destination_location"]["name"] == "Patio trasero"
    assert body["previous_orientation"] == "NE" and body["new_orientation"] == "N"

    fc = people["admin"].get(f"/api/v1/fog-collectors/{site['fc']['id']}").json()
    assert fc["location_id"] == site["patio"]["id"]
    assert fc["orientation"] == "N"
    history = db.scalars(
        select(DeviceLocation).where(DeviceLocation.device_id == site["device"]["id"]).order_by(DeviceLocation.id)
    ).all()
    # La estación tomó la ubicación del atrapanieblas al registrarse y se trasladó con él.
    assert [h.location_id for h in history] == [site["origin"]["id"], site["patio"]["id"]]
    assert history[0].ended_at is not None and history[1].ended_at is None

    titles = [n["title"] for n in people["docente"].get("/api/v1/notifications").json()["items"]]
    assert titles[0] == "Reubicación finalizada" and len(titles) == 3
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "fog_collector_relocation")))
    assert actions == {"reubicacion.solicitar", "reubicacion.aceptar", "reubicacion.iniciar", "reubicacion.finalizar"}
    # El director supervisa todo el proceso; un docente ajeno no ve la solicitud.
    assert people["director"].get(RELOCATIONS, params={"scope": "all"}).json()["total"] == 1
    assert people["docente2"].get(f"{RELOCATIONS}/{r['id']}").status_code == 404


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"proposed_location_id": "origin"}, "misma_ubicacion"),
        ({"proposed_location_id": 999_999}, "ubicacion_invalida"),
        ({"fog_collector_id": 999_999}, "referencia_inexistente"),
    ],
)
def test_request_respects_fog_collector_and_location_data(people, site, overrides, code):
    if overrides.get("proposed_location_id") == "origin":
        overrides = {"proposed_location_id": site["origin"]["id"]}
    response = request(people["docente"], site, **overrides)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_request_schema_validation(people, site):
    both = request(people["docente"], site, proposed_place="Junto al invernadero 2")
    assert both.status_code == 422
    short = request(people["docente"], site, description="corto")
    assert short.status_code == 422
    unknown = request(people["docente"], site, reason="capricho")
    assert unknown.status_code == 422


def test_only_one_request_in_progress_per_fog_collector(people, site):
    created(people["docente"], site)
    second = request(people["docente2"], site, proposed_location_id=site["huerto"]["id"])
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "reubicacion_en_curso"


def test_inactive_fog_collector_or_destination_is_rejected(people, site):
    people["admin"].delete(f"/api/v1/locations/{site['huerto']['id']}")
    inactive_dest = request(people["docente"], site, proposed_location_id=site["huerto"]["id"])
    assert inactive_dest.json()["error"]["code"] == "ubicacion_invalida"
    people["admin"].delete(f"/api/v1/fog-collectors/{site['fc']['id']}")
    assert request(people["docente"], site).json()["error"]["code"] == "atrapanieblas_inactivo"


def test_finish_requires_a_different_active_destination(people, site):
    r = created(people["docente"], site)
    tecnico = people["tecnico"]
    tecnico.post(f"{RELOCATIONS}/{r['id']}/accept")
    early = tecnico.post(f"{RELOCATIONS}/{r['id']}/finish", json=finish_payload(site))
    assert early.json()["error"]["code"] == "transicion_invalida"
    tecnico.post(f"{RELOCATIONS}/{r['id']}/start")
    same = tecnico.post(
        f"{RELOCATIONS}/{r['id']}/finish", json=finish_payload(site, destination_location_id=site["origin"]["id"])
    )
    assert same.json()["error"]["code"] == "misma_ubicacion"
    bad_orientation = tecnico.post(f"{RELOCATIONS}/{r['id']}/finish", json=finish_payload(site, new_orientation="X"))
    assert bad_orientation.status_code == 422
    # Sin orientación nueva se conserva la actual.
    kept = tecnico.post(f"{RELOCATIONS}/{r['id']}/finish", json=finish_payload(site, new_orientation=None))
    assert kept.status_code == 200
    assert people["admin"].get(f"/api/v1/fog-collectors/{site['fc']['id']}").json()["orientation"] == "NE"


def test_reject_before_starting_and_request_again(people, site):
    r = created(people["docente"], site)
    assert (
        people["docente"].post(f"{RELOCATIONS}/{r['id']}/reject", json={"reason": "No hay espacio libre."}).status_code
        == 403
    )
    short = people["tecnico"].post(f"{RELOCATIONS}/{r['id']}/reject", json={"reason": "no"})
    assert short.status_code == 422
    rejected = people["tecnico"].post(
        f"{RELOCATIONS}/{r['id']}/reject", json={"reason": "El patio se usa para formaciones escolares."}
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rechazado"
    assert rejected.json()["assignee"]["username"] == "tecnico1"
    # Una solicitud rechazada ya no está en curso: se puede volver a solicitar.
    again = created(people["docente"], site, proposed_location_id=site["huerto"]["id"])
    people["tecnico"].post(f"{RELOCATIONS}/{again['id']}/accept")
    people["tecnico"].post(f"{RELOCATIONS}/{again['id']}/start")
    late = people["tecnico"].post(f"{RELOCATIONS}/{again['id']}/reject", json={"reason": "Ya no conviene moverlo."})
    assert late.json()["error"]["code"] == "transicion_invalida"


def test_permissions_by_role(people, site):
    r = created(people["docente"], site)
    assert people["docente"].post(f"{RELOCATIONS}/{r['id']}/accept").status_code == 403
    assert people["docente"].get(RELOCATIONS, params={"scope": "all"}).status_code == 403
    assert request(people["tecnico"], site).status_code == 403
    summary = people["tecnico"].get(f"{RELOCATIONS}/summary").json()
    assert summary["open"] == 1 and summary["mine"] is None


def test_direct_edit_cannot_move_a_fog_collector_with_a_request_in_progress(people, site):
    created(people["docente"], site)
    admin = people["admin"]
    moved = admin.put(f"/api/v1/fog-collectors/{site['fc']['id']}", json={"location_id": site["huerto"]["id"]})
    assert moved.status_code == 409
    assert admin.delete(f"/api/v1/fog-collectors/{site['fc']['id']}").status_code == 409
    # Otros datos del atrapanieblas sí se pueden corregir.
    assert (
        admin.put(f"/api/v1/fog-collectors/{site['fc']['id']}", json={"mesh_type": "Raschel 35 %"}).status_code == 200
    )
    overview = admin.get("/api/v1/fog-collectors/overview").json()
    assert overview[0]["active_relocation"]["status"] == "pendiente"
