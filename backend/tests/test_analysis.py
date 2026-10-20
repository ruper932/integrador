"""Análisis estadístico: secciones por permiso y cálculos sobre datos conocidos."""

import pytest

from app.business.rules.statistics import describe, pearson, strength
from tests.test_iot import batch, headers, reading, station  # noqa: F401
from tests.test_reports import with_data  # noqa: F401

ANALYSIS = "/api/v1/analysis"


def test_describe_and_pearson():
    summary = describe([1.0, 2.0, 3.0, 4.0])
    assert (summary.n, summary.mean, summary.median, summary.min, summary.max) == (4, 2.5, 2.5, 1.0, 4.0)
    assert summary.std == pytest.approx(1.291, abs=1e-3)
    assert describe([]).mean is None
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert pearson([1, 2], [1, 2]) is None  # menos de 3 pares
    assert pearson([1, 1, 1], [1, 2, 3]) is None  # serie constante
    assert strength(0.8) == "fuerte positiva"
    assert strength(-0.4) == "moderada negativa"
    assert strength(None) == "sin datos suficientes"


def test_analysis_summarizes_capture_and_quality(admin_client, with_data):  # noqa: F811
    body = admin_client.get(ANALYSIS).json()
    capture = body["capture"]
    assert capture["total"] == pytest.approx(4.0)
    assert capture["days_with_data"] == 1
    assert capture["days_with_capture"] == 1
    quality = body["quality"]
    assert quality["by_quality"]["sin_dato"] == 1  # el valor no medido no se cuenta como 0
    assert quality["total"] == 4
    temperature = next(v for v in body["variables"] if v["code"] == "temperatura")
    assert temperature["mean"] == pytest.approx(12)
    temp_pairs = next(c for c in body["correlations"] if c["code"] == "temperatura")["points"]
    assert temp_pairs == [{"date": temp_pairs[0]["date"], "x": pytest.approx(12), "y": pytest.approx(4.0)}]
    assert {"maintenance", "incidents", "inventory"} <= body.keys()


def test_analysis_permissions(make_client, factory):
    director = factory.client_for(make_client(), "dir-an", ["director"])
    assert director.get(ANALYSIS).status_code == 200
    for role in ("docente", "mantenimiento"):
        assert factory.client_for(make_client(), f"{role}-an", [role]).get(ANALYSIS).status_code == 403


def test_analysis_rejects_invalid_range(admin_client):
    response = admin_client.get(
        ANALYSIS, params={"date_from": "2026-10-10T00:00:00Z", "date_to": "2026-10-01T00:00:00Z"}
    )
    assert response.json()["error"]["code"] == "rango_invalido"
