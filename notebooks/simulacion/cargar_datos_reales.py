"""Paso 1 (datos reales) — Convierte un CSV de la estación al formato horario de la simulación.

El archivo no se edita a mano: este script detecta separador, decimales, columna de fecha y hora,
variables (por nombre, en español o inglés) y si el volumen es incremental o acumulado, y deja un
informe de lo que detectó. Los valores ausentes se conservan como vacíos (nunca como 0).
"""

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "America/La_Paz"
INSTANT = ["temperatura", "humedad_relativa", "presion_atmosferica", "velocidad_viento", "direccion_viento", "niebla", "nivel_almacenamiento"]

# Variable canónica → patrones (sobre el nombre normalizado). Se prueban en este orden.
PATTERNS: list[tuple[str, list[str]]] = [
    ("direccion_viento", [r"dir", r"wind_?dir", r"wd\b"]),
    ("velocidad_viento", [r"vel.*vien", r"vien.*vel", r"wind_?speed", r"\bws\b", r"viento", r"wind", r"anemo"]),
    ("humedad_relativa", [r"hum", r"\brh\b", r"hr\b"]),
    ("temperatura", [r"temp", r"\bt_?aire", r"\bta\b"]),
    ("presion_atmosferica", [r"pres", r"press", r"baro", r"hpa"]),
    ("niebla", [r"niebla", r"fog", r"neblina"]),
    ("nivel_almacenamiento", [r"nivel", r"level", r"tanque", r"tank", r"distan"]),
    ("volumen_captado", [r"vol", r"litro", r"agua", r"caudal", r"flow", r"pluvi", r"lluvia", r"rain", r"precip", r"capta", r"pulso", r"tip"]),
]
DATE_HINTS = [r"fecha_?hora", r"timestamp", r"datetime", r"date_?time", r"measured", r"tiempo", r"time", r"fecha", r"date"]
TIME_HINTS = [r"^hora$", r"^time$", r"hora", r"hour"]


def normalize(name: str) -> str:
    plain = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", plain.lower()).strip("_")


def read_csv(path: Path) -> tuple[pd.DataFrame, dict]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    first = next((line for line in raw.splitlines() if line.strip()), "")
    sep = max([",", ";", "\t", "|"], key=first.count)
    frame = pd.read_csv(path, sep=sep, encoding="utf-8-sig", dtype=str, skipinitialspace=True)
    frame = frame.dropna(axis=1, how="all")
    return frame, {"separador": {"\t": "tabulador"}.get(sep, sep), "filas": len(frame), "columnas_originales": list(frame.columns)}


def to_number(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip().replace({"": None, "nan": None, "NaN": None, "null": None, "NULL": None, "-": None})
    # Decimal con coma (p. ej. «12,5») cuando no hay punto en el valor.
    text = text.where(text.isna() | text.str.contains(r"\."), text.str.replace(",", ".", regex=False))
    return pd.to_numeric(text.str.replace(r"[^0-9eE+\-.]", "", regex=True), errors="coerce")


def find_timestamp(frame: pd.DataFrame) -> tuple[pd.Series, str]:
    names = {c: normalize(c) for c in frame.columns}
    date_col = next((c for pat in DATE_HINTS for c, n in names.items() if re.search(pat, n)), None)
    if date_col is None:
        # Sin nombre reconocible: la primera columna que se interprete mayoritariamente como fecha.
        for c in frame.columns:
            parsed = pd.to_datetime(frame[c], errors="coerce", dayfirst=True)
            if parsed.notna().mean() > 0.9:
                date_col = c
                break
    if date_col is None:
        raise SystemExit("No se encontró una columna de fecha y hora en el archivo.")
    text = frame[date_col].astype(str)
    time_col = next(
        (c for pat in TIME_HINTS for c, n in names.items() if c != date_col and re.search(pat, n)), None
    )
    if time_col is not None and not text.str.contains(r"\d{1,2}:\d{2}").any():
        text = text + " " + frame[time_col].astype(str)
    # Se elige la interpretación (día primero o mes primero) que produce más fechas válidas y ordenadas.
    best = None
    for dayfirst in (True, False):
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=dayfirst, format="mixed")
        score = (parsed.notna().mean(), parsed.dropna().is_monotonic_increasing)
        if best is None or score > best[0]:
            best = (score, parsed, dayfirst)
    parsed = best[1]
    if parsed.dt.tz is None:
        parsed = parsed.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="NaT")
    used = date_col if time_col is None or text is frame[date_col] else f"{date_col} + {time_col}"
    return parsed.dt.tz_convert("UTC"), used


def map_columns(frame: pd.DataFrame, skip: set[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for canonical, patterns in PATTERNS:
        for column in frame.columns:
            if column in skip or column in mapping.values():
                continue
            name = normalize(column)
            if any(re.search(p, name) for p in patterns) and to_number(frame[column]).notna().mean() > 0.3:
                mapping[canonical] = column
                break
    return mapping


def volume_kind(values: pd.Series) -> str:
    """«acumulado» si el valor casi nunca baja y sube con frecuencia (contador); si no, «incremental»."""
    steps = values.dropna().diff().dropna()
    if len(steps) < 10:
        return "incremental"
    never_drops = (steps >= 0).mean() > 0.97
    grows = (steps > 0).mean() > 0.2 and values.dropna().iloc[-1] > values.dropna().iloc[0]
    return "acumulado" if never_drops and grows else "incremental"


def main(source: Path, output_dir: Path) -> tuple[Path, dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frame, info = read_csv(source)
    timestamps, ts_column = find_timestamp(frame)
    mapping = map_columns(frame, skip={c.strip() for c in ts_column.split(" + ")})
    data = pd.DataFrame({"measured_at": timestamps})
    for canonical, column in mapping.items():
        data[canonical] = to_number(frame[column]).to_numpy()
    data = data.dropna(subset=["measured_at"]).sort_values("measured_at").drop_duplicates("measured_at")

    kind = None
    if "volumen_captado" in data:
        kind = volume_kind(data["volumen_captado"])
        if kind == "acumulado":
            # Diferencias entre lecturas; un descenso es un reinicio del contador, no captación negativa.
            diff = data["volumen_captado"].diff()
            data["volumen_captado"] = diff.where(diff >= 0)
        data.loc[data["volumen_captado"] < 0, "volumen_captado"] = np.nan

    interval = data["measured_at"].diff().median()
    indexed = data.set_index("measured_at")
    hourly = indexed.resample("1h").agg(
        {**{c: "mean" for c in INSTANT if c in indexed}, **({"volumen_captado": lambda s: s.sum(min_count=1)} if "volumen_captado" in indexed else {})}
    )
    for column in ["temperatura", "humedad_relativa", "presion_atmosferica", "velocidad_viento", "direccion_viento", "niebla", "volumen_captado"]:
        if column not in hourly:
            hourly[column] = np.nan  # variable no medida: vacía, nunca 0
    hourly = hourly.reset_index()
    path = output_dir / "lecturas_horarias_reales.csv"
    hourly.to_csv(path, index=False)

    report = {
        **info,
        "columna_fecha": ts_column,
        "variables_detectadas": mapping,
        "columnas_no_usadas": [c for c in frame.columns if c not in mapping.values() and c not in ts_column],
        "volumen": kind,
        "intervalo_mediano_entre_lecturas": str(interval),
        "desde": str(data["measured_at"].min().tz_convert(TZ)),
        "hasta": str(data["measured_at"].max().tz_convert(TZ)),
        "dias_con_datos": int(hourly.dropna(subset=list(mapping), how="all")["measured_at"].dt.tz_convert(TZ).dt.date.nunique()),
        "horas": len(hourly),
        "porcentaje_vacios_por_variable": {c: round(float(hourly[c].isna().mean() * 100), 1) for c in mapping},
    }
    (output_dir / "deteccion.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, report


if __name__ == "__main__":
    import sys

    base = Path(__file__).resolve().parents[2]
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "data" / "último paquete.csv"
    print(json.dumps(main(source, Path(__file__).parent / "salidas_reales")[1], ensure_ascii=False, indent=2))
