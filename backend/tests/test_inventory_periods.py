"""Sistema de inventario periódico: periodos, conteo físico, ajustes, cierre y valorización."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.data.models.inventory import InventoryMovement

ITEMS = "/api/v1/inventory/items"
PERIODS = "/api/v1/inventory/periods"


def at(year, month, day, hour=12):
    return datetime(year, month, day, hour, tzinfo=UTC)


def D(value):  # noqa: N802
    return Decimal(str(value))


def category_id(client):
    return client.get("/api/v1/inventory/categories").json()[0]["id"]


def create_item(client, code="CABLE-UTP", **extra):
    payload = {"code": code, "name": f"Repuesto {code}", "category_id": category_id(client), "unit": "metro"}
    payload.update(extra)
    response = client.post(ITEMS, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def move(client, item_id, kind, qty, unit_cost=None, reason="Movimiento de prueba"):
    body = {"movement_type": kind, "quantity": str(qty), "reason": reason}
    if unit_cost is not None:
        body["unit_cost"] = str(unit_cost)
    return client.post(f"{ITEMS}/{item_id}/movements", json=body)


def create_period(client, name, start, end):
    response = client.post(PERIODS, json={"name": name, "start_date": start, "end_date": end})
    assert response.status_code == 201, response.text
    return response.json()


def count(client, period_id, item_id, qty):
    return client.put(
        f"{PERIODS}/{period_id}/counts", json={"counts": [{"item_id": item_id, "counted_quantity": str(qty)}]}
    )


@pytest.fixture
def september(admin_client, travel):
    """Septiembre 2026: stock inicial 10 a Bs 5, entrada 10 a Bs 8, salida 4."""
    period = create_period(admin_client, "Septiembre 2026", "2026-09-01", "2026-09-30")
    travel(at(2026, 9, 2))
    item = create_item(admin_client, initial_stock="10", initial_unit_cost="5")
    travel(at(2026, 9, 10))
    assert move(admin_client, item["id"], "entrada", 10, unit_cost=8).status_code == 201
    travel(at(2026, 9, 15))
    assert move(admin_client, item["id"], "salida", 4).status_code == 201
    travel(None)
    return period, item


def test_open_period_shows_provisional_balances(admin_client, september):
    period, item = september
    summary = admin_client.get(f"{PERIODS}/{period['id']}").json()
    assert summary["provisional"] is True
    assert summary["pending_count_items"] == 1
    balance = summary["balances"][0]
    assert D(balance["entries_quantity"]) == 20
    assert D(balance["exits_quantity"]) == 4
    assert D(balance["theoretical_quantity"]) == 16
    assert balance["counted_quantity"] is None


def test_close_requires_all_counts(admin_client, september):
    period, _ = september
    response = admin_client.post(f"{PERIODS}/{period['id']}/close")
    assert response.json()["error"]["code"] == "conteo_incompleto"
    assert response.json()["error"]["details"]["faltantes"] == ["CABLE-UTP"]


def test_close_generates_adjustment_freezes_balances_and_values(admin_client, september, db):
    period, item = september
    assert count(admin_client, period["id"], item["id"], 15).status_code == 200  # falta 1 metro

    closed = admin_client.post(f"{PERIODS}/{period['id']}/close")
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body["provisional"] is False
    assert body["period"]["status"] == "cerrado"
    balance = body["balances"][0]
    assert D(balance["opening_quantity"]) == 0
    assert D(balance["theoretical_quantity"]) == 16
    assert D(balance["counted_quantity"]) == 15
    assert D(balance["difference"]) == -1
    assert D(balance["adjustments_quantity"]) == -1
    assert D(balance["closing_quantity"]) == 15
    # Costo promedio ponderado: (10×5 + 10×8) / 20 = 6,5 → 15 × 6,5 = 97,5
    assert D(balance["average_unit_cost"]) == D("6.5")
    assert D(balance["closing_value"]) == D("97.5")
    assert D(body["total_value"]) == D("97.5")

    # El ajuste es un movimiento trazable fechado al final del periodo y corrige el stock actual.
    adjustment = db.scalars(
        select(InventoryMovement).where(InventoryMovement.reason.like("Ajuste por conteo físico%"))
    ).one()
    assert adjustment.movement_type.code == "ajuste_faltante"
    assert adjustment.occurred_at.astimezone().date().isoformat() <= "2026-10-01"
    assert D(admin_client.get(f"{ITEMS}/{item['id']}").json()["current_stock"]) == 15


def test_closed_period_is_immutable(admin_client, september, travel):
    period, item = september
    count(admin_client, period["id"], item["id"], 16)
    admin_client.post(f"{PERIODS}/{period['id']}/close")
    assert count(admin_client, period["id"], item["id"], 1).json()["error"]["code"] == "periodo_cerrado"
    assert admin_client.post(f"{PERIODS}/{period['id']}/close").json()["error"]["code"] == "periodo_cerrado"
    travel(at(2026, 9, 20))
    blocked = move(admin_client, item["id"], "salida", 1)
    assert blocked.json()["error"]["code"] == "periodo_cerrado"
    travel(None)
    # Fuera del periodo cerrado sí se registran movimientos.
    assert move(admin_client, item["id"], "salida", 1).status_code == 201


def test_period_rules(admin_client, september, travel):
    period, item = september
    overlap = admin_client.post(PERIODS, json={"name": "Otro", "start_date": "2026-09-15", "end_date": "2026-10-15"})
    assert overlap.json()["error"]["code"] == "periodo_superpuesto"
    reversed_dates = admin_client.post(
        PERIODS, json={"name": "Invertido", "start_date": "2027-02-01", "end_date": "2027-01-01"}
    )
    assert reversed_dates.json()["error"]["code"] == "rango_invalido"
    current = create_period(admin_client, "Octubre 2026", "2026-10-01", "2026-10-31")
    count(admin_client, current["id"], item["id"], 16)
    travel(at(2026, 10, 15))  # octubre en curso, sin depender de la fecha real
    in_course = admin_client.post(f"{PERIODS}/{current['id']}/close")
    travel(None)
    assert in_course.json()["error"]["code"] == "periodo_en_curso"
    # Los periodos se cierran en orden.
    create_period(admin_client, "Agosto 2026", "2026-08-01", "2026-08-31")
    count(admin_client, period["id"], item["id"], 16)
    out_of_order = admin_client.post(f"{PERIODS}/{period['id']}/close")
    assert out_of_order.json()["error"]["code"] == "periodo_anterior_abierto"


def test_valuation_carries_over_between_periods(admin_client, travel):
    july = create_period(admin_client, "Julio 2026", "2026-07-01", "2026-07-31")
    august = create_period(admin_client, "Agosto 2026", "2026-08-01", "2026-08-31")
    travel(at(2026, 7, 5))
    item = create_item(admin_client, code="SHT31", unit="unidad", initial_stock="10", initial_unit_cost="4")
    travel(at(2026, 8, 5))
    move(admin_client, item["id"], "entrada", 10, unit_cost=6)
    travel(None)

    count(admin_client, july["id"], item["id"], 10)
    jul = admin_client.post(f"{PERIODS}/{july['id']}/close").json()["balances"][0]
    assert D(jul["closing_value"]) == 40

    count(admin_client, august["id"], item["id"], 20)
    aug = admin_client.post(f"{PERIODS}/{august['id']}/close").json()["balances"][0]
    assert D(aug["opening_quantity"]) == 10
    assert D(aug["opening_value"]) == 40
    assert D(aug["average_unit_cost"]) == 5  # (40 + 60) / 20
    assert D(aug["closing_value"]) == 100


def test_missing_unit_cost_makes_valuation_unknown(admin_client, travel):
    period = create_period(admin_client, "Mayo 2026", "2026-05-01", "2026-05-31")
    travel(at(2026, 5, 3))
    item = create_item(admin_client, code="DONADO", unit="unidad", initial_stock="3")  # donación sin costo
    travel(None)
    count(admin_client, period["id"], item["id"], 3)
    body = admin_client.post(f"{PERIODS}/{period['id']}/close").json()
    assert body["balances"][0]["closing_value"] is None
    assert body["total_value"] is None


def test_unit_cost_only_on_entries_and_permissions(admin_client, make_client, factory):
    item = create_item(admin_client, code="TORNILLO", unit="unidad", initial_stock="5")
    assert move(admin_client, item["id"], "salida", 1, unit_cost=2).json()["error"]["code"] == "costo_invalido"
    manual_adjustment = admin_client.post(
        f"{ITEMS}/{item['id']}/movements", json={"movement_type": "ajuste_sobrante", "quantity": "1", "reason": "x"}
    )
    assert manual_adjustment.status_code == 422
    director = factory.client_for(make_client(), "dir-inv", ["director"])
    assert director.get(PERIODS).status_code == 200
    forbidden = director.post(PERIODS, json={"name": "X", "start_date": "2026-01-01", "end_date": "2026-01-31"})
    assert forbidden.status_code == 403


EXPORT = "/api/v1/reports/export"


def test_inventory_reports(admin_client, september):
    import io

    from openpyxl import load_workbook

    period, item = september
    # Planilla en blanco antes del conteo, acta después.
    blank = admin_client.get(EXPORT, params={"report": "inventario_conteo", "format": "pdf", "period_id": period["id"]})
    assert blank.status_code == 200 and blank.content.startswith(b"%PDF")
    count(admin_client, period["id"], item["id"], 15)
    admin_client.post(f"{PERIODS}/{period['id']}/close")

    summary = admin_client.get(
        EXPORT, params={"report": "inventario_periodo", "format": "xlsx", "period_id": period["id"]}
    )
    rows = list(load_workbook(io.BytesIO(summary.content))["Detalle"].iter_rows(values_only=True))
    data = next(r for r in rows if r[0] == "CABLE-UTP")
    assert data[3:9] == (0, 20, 4, 0, -1, 15)
    assert rows[-1][0] == "TOTAL" and rows[-1][10] == pytest.approx(97.5)

    acta = admin_client.get(EXPORT, params={"report": "inventario_conteo", "format": "csv", "period_id": period["id"]})
    assert "Faltante" in acta.text

    kardex = admin_client.get(
        EXPORT,
        params={
            "report": "inventario_kardex",
            "format": "xlsx",
            "item_id": item["id"],
            "date_from": "2026-09-01T00:00:00-04:00",
            "date_to": "2026-10-01T00:00:00-04:00",
        },
    )
    krows = list(load_workbook(io.BytesIO(kardex.content))["Detalle"].iter_rows(values_only=True))
    saldos = [r[6] for r in krows if isinstance(r[6], (int, float))]
    assert saldos == [0, 10, 20, 16, 15]  # inicial, stock inicial, entrada, salida, ajuste

    assert (
        admin_client.get(EXPORT, params={"report": "inventario_periodo"}).json()["error"]["code"] == "periodo_requerido"
    )
    assert (
        admin_client.get(EXPORT, params={"report": "inventario_kardex"}).json()["error"]["code"] == "repuesto_requerido"
    )
    assert admin_client.get(EXPORT, params={"report": "inventario_consumo", "format": "pdf"}).status_code == 200
