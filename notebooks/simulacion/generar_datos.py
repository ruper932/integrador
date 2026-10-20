"""Paso 1 — Generación de datos horarios SINTÉTICOS de una estación de atrapanieblas.

Los datos imitan la forma que tendrán las lecturas reales (mismas variables, unidades,
valores null por fallas de sensor) pero NO representan mediciones reales de Titicachi.
Sirven únicamente para probar el flujo de preparación, entrenamiento y evaluación.

Supuestos del generador (ajustables):
- Estacionalidad: más niebla en la época de lluvias (diciembre–marzo) que en la seca (mayo–agosto).
- La niebla persiste por episodios (proceso de Markov horario) y es más probable de noche/madrugada.
- Régimen húmedo diario persistente (AR(1), φ = 0,75): representa sistemas de tiempo que duran
  varios días; aumenta la probabilidad de niebla y la humedad, y baja la presión.
- La captación depende de la intensidad de niebla, la velocidad del viento (óptimo intermedio)
  y la humedad cercana a saturación, multiplicada por el área de malla. Escala de referencia:
  del orden de 1–5 L/m²/día en días de niebla (valores citados para atrapanieblas de malla Raschel).
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2026
DAYS = 730
MESH_AREA_M2 = 40.0
SENSOR_GAP_RATE = 0.02  # fracción de lecturas faltantes (se representan como NaN/null, nunca 0)


def generate(days: int = DAYS, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-01", periods=days * 24, freq="h", tz="America/La_Paz")
    n = len(index)
    doy = index.dayofyear.to_numpy()
    hour = index.hour.to_numpy()

    # Estacionalidad: máximo de niebla hacia fines de enero, mínimo a mediados de año.
    season = 0.5 + 0.5 * np.cos(2 * np.pi * (doy - 30) / 365.25)
    nocturnal = 0.5 + 0.5 * np.cos(2 * np.pi * (hour - 4) / 24)

    # Régimen húmedo diario (persistente entre días), interpolado a escala horaria.
    regime_daily = np.zeros(days)
    for d in range(1, days):
        regime_daily[d] = 0.75 * regime_daily[d - 1] + rng.normal(0, 0.66)
    regime = np.repeat(regime_daily, 24)
    regime_boost = 1 / (1 + np.exp(-1.5 * regime))  # 0..1

    # Episodios de niebla persistentes.
    fog_state = np.zeros(n, dtype=bool)
    for i in range(1, n):
        p_start = 0.01 + 0.14 * season[i] * nocturnal[i] * (0.3 + 1.4 * regime_boost[i])
        p_stay = 0.80 + 0.12 * season[i]
        fog_state[i] = rng.random() < (p_stay if fog_state[i - 1] else p_start)
    fog = np.where(fog_state, rng.uniform(40, 100, n), rng.uniform(0, 15, n))

    temperature = 9 + 3 * season + 5 * np.sin(2 * np.pi * (hour - 9) / 24) - 2.5 * fog_state + rng.normal(0, 1.0, n)
    humidity = np.clip(62 + 12 * season + 8 * regime_boost + 0.3 * fog + rng.normal(0, 4, n), 20, 100)
    wind = np.clip(2.5 + 2.0 * np.sin(2 * np.pi * (hour - 14) / 24) + rng.gamma(2.0, 0.7, n), 0, 20)
    direction = (110 + 40 * np.sin(2 * np.pi * doy / 365.25) + rng.normal(0, 35, n)) % 360
    pressure = 750 + 3 * np.sin(2 * np.pi * doy / 365.25) - 2.5 * regime - 1.0 * fog_state + rng.normal(0, 0.8, n)

    # Captación horaria (litros) — valor incremental.
    wind_eff = np.exp(-((wind - 4.5) ** 2) / (2 * 2.2**2))
    humidity_eff = np.clip((humidity - 85) / 15, 0, 1)
    liters_per_m2 = 0.35 * (fog / 100) ** 1.5 * wind_eff * (0.3 + 0.7 * humidity_eff)
    volume = np.clip(MESH_AREA_M2 * liters_per_m2 * rng.lognormal(0, 0.25, n), 0, None)
    volume = np.where(fog_state, volume, volume * 0.05)

    df = pd.DataFrame(
        {
            "measured_at": index,
            "temperatura": temperature.round(1),
            "humedad_relativa": humidity.round(1),
            "presion_atmosferica": pressure.round(1),
            "velocidad_viento": wind.round(2),
            "direccion_viento": direction.round(0),
            "niebla": fog.round(1),
            "volumen_captado": volume.round(3),
        }
    )
    # Fallas de sensor: la variable queda sin dato (NaN), no en cero.
    for column in df.columns[1:]:
        df.loc[rng.random(n) < SENSOR_GAP_RATE, column] = np.nan
    return df


def main(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "lecturas_horarias_sinteticas.csv"
    generate().to_csv(path, index=False)
    return path


if __name__ == "__main__":
    print(main(Path(__file__).parent / "salidas"))
