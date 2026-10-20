"""Carga de datos de demostración."""

import pytest
from sqlalchemy import func, select

from app.data.models.incidents import IncidentReport
from app.data.models.inventory import InventoryPeriod, MaintenanceRecord
from app.data.models.iot import Device, SensorReading
from app.data.models.security import Role, User, user_roles
from app.demo_data import DEMO_PASSWORD, DemoSeeder, SeedError


def test_seed_demo_loads_every_module_and_is_not_repeatable(factory, db, client):
    factory.user("admin", roles=["administrador"])
    result = DemoSeeder(db).run()
    assert result["usuarios"] == 6

    per_role = dict(
        db.execute(
            select(Role.name, func.count()).join(user_roles, user_roles.c.role_id == Role.id).group_by(Role.name)
        ).all()
    )
    assert per_role["director"] == per_role["docente"] == per_role["mantenimiento"] == 2
    statuses_by_report = sorted(r.status for r in db.scalars(select(IncidentReport)))
    assert statuses_by_report == ["abierto", "aceptado", "en_progreso", "finalizado", "finalizado"]
    assert db.scalar(select(func.count()).select_from(Device)) == 3
    assert db.scalar(select(func.count()).select_from(SensorReading)) > 10_000
    assert db.scalar(select(func.count()).select_from(MaintenanceRecord)) == 9
    statuses = sorted(db.scalars(select(InventoryPeriod.status)).all())
    assert statuses == ["abierto", "cerrado", "cerrado"]
    assert all(u.profile_complete for u in db.scalars(select(User).where(User.username != "admin")))

    # Las cuentas de demostración ingresan con la contraseña común.
    response = client.post("/api/v1/auth/login", json={"username": "mhuanca", "password": DEMO_PASSWORD})
    assert response.status_code == 200
    assert response.json()["user"]["must_change_password"] is False

    with pytest.raises(SeedError):
        DemoSeeder(db).run()


def test_seed_demo_requires_an_admin(db):
    with pytest.raises(SeedError):
        DemoSeeder(db)
