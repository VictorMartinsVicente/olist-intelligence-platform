"""
API que serve o modelo de previsão de risco de atraso na entrega.

Rodar localmente (fora do Docker):
    uvicorn api.main:app --reload --port 8000

Depois acesse http://localhost:8000/docs para o Swagger interativo.
"""
import os

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MODEL_PATH = os.environ.get(
    "MODEL_PATH",
    os.path.join(os.path.dirname(__file__), "..", "ml", "artifacts", "model.pkl"),
)

app = FastAPI(
    title="Olist Delivery Delay Prediction API",
    description="Prevê a probabilidade de um pedido atrasar, com base em dados do pedido no momento da compra.",
    version="1.0.0",
)

_model = None


def get_model():
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Modelo não encontrado em {MODEL_PATH}. "
                    "Rode 'python ml/train.py' antes de subir a API."
                ),
            )
        _model = joblib.load(MODEL_PATH)
    return _model


class OrderFeatures(BaseModel):
    estimated_delivery_days: float = Field(..., json_schema_extra={"example": 12.5}, description="Prazo estimado em dias")
    order_total_value: float = Field(..., json_schema_extra={"example": 189.90}, description="Valor total do pedido")
    avg_freight_value: float = Field(..., json_schema_extra={"example": 22.30}, description="Valor médio do frete")
    n_items: int = Field(..., json_schema_extra={"example": 1}, description="Número de itens no pedido")
    payment_installments: int = Field(..., json_schema_extra={"example": 3}, description="Número de parcelas")
    purchase_month: int = Field(..., ge=1, le=12, json_schema_extra={"example": 11}, description="Mês da compra (1-12)")
    purchase_day_of_week: int = Field(..., ge=0, le=6, json_schema_extra={"example": 4}, description="Dia da semana (0=segunda)")
    customer_state: str = Field(..., json_schema_extra={"example": "SP"}, description="Estado do cliente (sigla)")
    primary_seller_state: str = Field(..., json_schema_extra={"example": "SP"}, description="Estado do vendedor (sigla)")
    primary_product_category: str = Field(..., json_schema_extra={"example": "informatica_acessorios"})
    payment_type: str = Field(..., json_schema_extra={"example": "credit_card"})


class PredictionResponse(BaseModel):
    delay_probability: float
    is_delayed_prediction: bool
    risk_level: str


def _risk_level(prob: float) -> str:
    if prob >= 0.7:
        return "alto"
    if prob >= 0.4:
        return "medio"
    return "baixo"


@app.get("/health")
def health():
    model_exists = os.path.exists(MODEL_PATH)
    return {"status": "ok", "model_loaded": model_exists}


@app.post("/predict", response_model=PredictionResponse)
def predict(order: OrderFeatures):
    model = get_model()
    df = pd.DataFrame([order.model_dump()])

    try:
        proba = float(model.predict_proba(df)[0][1])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Erro ao gerar previsão: {e}")

    return PredictionResponse(
        delay_probability=round(proba, 4),
        is_delayed_prediction=proba >= 0.5,
        risk_level=_risk_level(proba),
    )


@app.get("/")
def root():
    return {
        "message": "Olist Delivery Delay Prediction API",
        "docs": "/docs",
        "health": "/health",
    }
