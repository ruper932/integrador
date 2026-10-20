import itertools

from tests.factories import DEFAULT_PASSWORD

_ci = itertools.count(5_000_000)


def profile(**overrides):
    data = {
        "first_names": "Juana",
        "paternal_surname": "Mamani",
        "maternal_surname": "Quispe",
        "ci_number": str(next(_ci)),
        "mobile_phone": "71234567",
        "birth_date": "1987-12-01",
    }
    data.update(overrides)
    return data


def role_id(admin_client, name):
    return next(r["id"] for r in admin_client.get("/api/v1/roles").json() if r["name"] == name)


def test_admin_creates_user_with_temporary_password(admin_client, make_client):
    response = admin_client.post(
        "/api/v1/users",
        json={
            "username": "docente1",
            "profile": profile(),
            "role_ids": [role_id(admin_client, "director")],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["temporary_password"]
    assert body["user"]["must_change_password"] is True

    new_client = make_client()
    login = new_client.post("/api/v1/auth/login", json={"username": "docente1", "password": body["temporary_password"]})
    assert login.status_code == 200
    assert login.json()["user"]["must_change_password"] is True


def test_duplicate_username_is_rejected(admin_client):
    payload = {"username": "repetido", "profile": profile(), "role_ids": [role_id(admin_client, "docente")]}
    assert admin_client.post("/api/v1/users", json=payload).status_code == 201
    assert admin_client.post("/api/v1/users", json=payload).status_code == 409


def test_deactivating_user_revokes_sessions_and_blocks_login(admin_client, make_client, factory):
    user = factory.user("temporal", roles=["docente"])
    user_client = factory.login(make_client(), "temporal")
    assert admin_client.delete(f"/api/v1/users/{user.id}").json()["is_active"] is False
    assert user_client.get("/api/v1/auth/me").status_code == 401
    retry = make_client().post("/api/v1/auth/login", json={"username": "temporal", "password": DEFAULT_PASSWORD})
    assert retry.status_code == 401


def test_admin_cannot_deactivate_self_or_last_admin(admin_client, factory):
    me = admin_client.get("/api/v1/auth/me").json()
    response = admin_client.delete(f"/api/v1/users/{me['id']}")
    assert response.status_code == 422
    observer = role_id(admin_client, "docente")
    response = admin_client.put(f"/api/v1/users/{me['id']}", json={"role_ids": [observer]})
    assert response.json()["error"]["code"] == "ultimo_administrador"


def test_admin_resets_password_and_invalidates_sessions(admin_client, make_client, factory):
    user = factory.user("olvidadizo", roles=["docente"])
    user_client = factory.login(make_client(), "olvidadizo")
    result = admin_client.post(f"/api/v1/users/{user.id}/reset-password", json={}).json()
    assert result["temporary_password"]
    assert user_client.get("/api/v1/auth/me").status_code == 401


def test_teacher_permissions(make_client, factory):
    teacher = factory.client_for(make_client(), "obs", ["docente"])
    assert teacher.get("/api/v1/dashboard/summary").status_code == 200
    assert teacher.get("/api/v1/measurements").status_code == 200
    assert teacher.get("/api/v1/users").status_code == 403
    assert teacher.get("/api/v1/inventory/items").status_code == 403
    assert teacher.post("/api/v1/devices", json={"code": "esp-x", "name": "ESP X"}).status_code == 403
    assert teacher.get("/api/v1/admin/recovery-requests").status_code == 403


def test_director_reads_inventory_but_cannot_modify(make_client, factory):
    director = factory.client_for(make_client(), "dir", ["director"])
    assert director.get("/api/v1/inventory/items").status_code == 200
    response = director.post(
        "/api/v1/inventory/items", json={"code": "X1", "name": "Cosa", "category_id": 1, "unit": "unidad"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "sin_permiso"


def test_admin_can_edit_role_permissions_but_not_admin_role(admin_client):
    roles = {r["name"]: r for r in admin_client.get("/api/v1/roles").json()}
    response = admin_client.put(
        f"/api/v1/roles/{roles['docente']['id']}",
        json={
            "permissions": ["dashboard.consultar", "mediciones.consultar", "reportes.consultar", "inventario.consultar"]
        },
    )
    assert response.status_code == 200
    assert len(response.json()["permissions"]) == 4
    response = admin_client.put(f"/api/v1/roles/{roles['administrador']['id']}", json={"permissions": []})
    assert response.status_code == 422


def test_audit_log_records_admin_actions(admin_client):
    admin_client.post(
        "/api/v1/users",
        json={"username": "auditado", "profile": profile(), "role_ids": [role_id(admin_client, "docente")]},
    )
    logs = admin_client.get("/api/v1/admin/audit-logs", params={"action": "usuario.crear"}).json()
    assert logs["total"] >= 1
    assert logs["items"][0]["username"] == "admin"
    assert "temporary_password" not in str(logs["items"][0]["details"])
