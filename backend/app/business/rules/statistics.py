"""Estadística descriptiva y correlación para el análisis (sin dependencias externas)."""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Summary:
    n: int
    mean: float | None
    median: float | None
    std: float | None  # desviación estándar muestral
    min: float | None
    max: float | None


def describe(values: Sequence[float]) -> Summary:
    """Resumen de valores medidos; los días sin dato no se incluyen (no se tratan como 0)."""
    if not values:
        return Summary(0, None, None, None, None, None)
    return Summary(
        n=len(values),
        mean=statistics.fmean(values),
        median=statistics.median(values),
        std=statistics.stdev(values) if len(values) > 1 else None,
        min=min(values),
        max=max(values),
    )


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Coeficiente de Pearson; None si hay menos de 3 pares o una serie es constante."""
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    try:
        return statistics.correlation(xs, ys)
    except statistics.StatisticsError:
        return None


def strength(r: float | None) -> str:
    if r is None:
        return "sin datos suficientes"
    size = abs(r)
    label = "débil" if size < 0.3 else "moderada" if size < 0.6 else "fuerte"
    return f"{label} {'positiva' if r > 0 else 'negativa'}" if size >= 0.1 else "sin relación apreciable"
