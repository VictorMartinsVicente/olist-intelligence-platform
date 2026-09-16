"""
Testes da API. Rodar com: pytest api/tests/test_api.py -v

[Framework] CRISP-DM: Deployment | TDSP: Deployment -- valida o contrato HTTP
do modelo em produção.

Os testes de /predict não dependem mais de alguém ter rodado ml/train.py antes:
o fixture ensure_model_exists() treina um modelo mínimo e rápido (poucas
centenas de linhas, LogisticRegression) só para o teste, se ainda não existir
um model.pkl real em MODEL_PATH. Isso torna o teste determinístico em qualquer
ambiente (CI, máquina nova, etc.) sem exigir um treino completo antes.
"""
import os

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import MODEL_PATH, app

client = TestClient(app)

SAMPLE_CSV = os.path.join(
    os.path.dirname(__file__), "..", "..", "analytics", "sample_fct_delivery_performance.csv"
)

VALID_ORDER_PAYLOAD = {
    "estimated_delivery_days": 12.5,
    "order_total_value": 189.90,
    "avg_freight_value": 22.30,
    "n_items": 1,
    "payment_installments": 3,
    "purchase_month": 11,
    "purchase_day_of_week": 4,
    "customer_state": "SP",
    "primary_seller_state": "SP",
    "primary_product_category": "informatica_acessorios",
    "payment_type": "credit_card",
}


@pytest.fixture(scope="module", autouse=True)
def ensure_model_exists():
    """Garante que existe um modelo em MODEL_PATH para os testes de /predict
    rodarem de forma determinística, sem depender de treino manual prévio.
    Se já existir um model.pkl real (ex: rodando localmente após treino de
    verdade), não mexe nele -- só treina um substituto se estiver ausente."""
    if os.path.exists(MODEL_PATH):
        yield
        return

    import joblib
    from sklearn.linear_model import LogisticRegression

    from ml.train import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET, build_pipeline

    df = pd.read_csv(SAMPLE_CSV).dropna(subset=NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET])
    pipeline = build_pipeline(LogisticRegression(max_iter=200))
    pipeline.fit(df[NUMERIC_FEATURES + CATEGORICAL_FEATURES], df[TARGET])

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)

    yield

    os.remove(MODEL_PATH)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_predict_missing_field_returns_422():
    payload = VALID_ORDER_PAYLOAD.copy()
    del payload["customer_state"]
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 422


def test_predict_invalid_month_returns_422():
    payload = VALID_ORDER_PAYLOAD.copy()
    payload["purchase_month"] = 13
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 422


def test_predict_valid_payload_returns_probability():
    resp = client.post("/predict", json=VALID_ORDER_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert 0.0 <= body["delay_probability"] <= 1.0
    assert body["risk_level"] in {"baixo", "medio", "alto"}
    assert isinstance(body["is_delayed_prediction"], bool)
