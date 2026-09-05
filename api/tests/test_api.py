"""
Testes da API. Rodar com: pytest api/tests/test_api.py -v

Nota: os testes de /predict pulam automaticamente (skip) se o modelo ainda não
foi treinado localmente (ml/artifacts/model.pkl inexistente) — isso permite
rodar `pytest` no CI mesmo antes do primeiro treino.
"""
import os

import pytest
from fastapi.testclient import TestClient

from api.main import MODEL_PATH, app

client = TestClient(app)

MODEL_EXISTS = os.path.exists(MODEL_PATH)

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


@pytest.mark.skipif(not MODEL_EXISTS, reason="Modelo ainda não treinado (rode ml/train.py)")
def test_predict_valid_payload_returns_probability():
    resp = client.post("/predict", json=VALID_ORDER_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert 0.0 <= body["delay_probability"] <= 1.0
    assert body["risk_level"] in {"baixo", "medio", "alto"}
    assert isinstance(body["is_delayed_prediction"], bool)
