"""Módulo PROVISIONAL: estimación del volumen con el modelo de ML y datos en vivo de las estaciones."""

from fastapi import APIRouter

from app.business.ml.prediction_service import ProvisionalPredictionService
from app.presentation.api.deps import CurrentAuth, DbSession
from app.presentation.schemas.ml import ProvisionalPredictionOut

router = APIRouter(tags=["Machine learning (provisional)"])


@router.get(
    "/ml/provisional",
    response_model=ProvisionalPredictionOut,
    summary="Volumen estimado para hoy por estación conectada (modelo provisional, cualquier rol)",
)
def provisional_estimates(db: DbSession, _: CurrentAuth) -> ProvisionalPredictionOut:
    return ProvisionalPredictionOut(**ProvisionalPredictionService(db).estimate())
