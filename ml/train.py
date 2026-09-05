"""
Treina um modelo de classificação para prever se um pedido vai atrasar,
usando os dados do mart marts.fct_delivery_performance (gerado pelo dbt).

Compara um baseline (regressão logística) contra um modelo mais forte (XGBoost),
loga tudo no MLflow (params, métricas, artifacts) e salva o melhor modelo em
ml/artifacts/model.pkl para a API servir.

Uso:
    python ml/train.py
"""
import os

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from sqlalchemy import create_engine

NUMERIC_FEATURES = [
    "estimated_delivery_days",
    "order_total_value",
    "avg_freight_value",
    "n_items",
    "payment_installments",
    "purchase_month",
    "purchase_day_of_week",
]
CATEGORICAL_FEATURES = [
    "customer_state",
    "primary_seller_state",
    "primary_product_category",
    "payment_type",
]
TARGET = "is_delayed"

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def get_engine():
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "olist")
    user = os.environ.get("POSTGRES_USER", "olist_user")
    password = os.environ.get("POSTGRES_PASSWORD", "olist_pass")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}")


def load_training_data(engine=None, csv_fallback: str = None) -> pd.DataFrame:
    """Carrega do mart no Postgres. Se não houver conexão, aceita um CSV de fallback
    (útil para rodar train.py isolado, sem banco, em ambiente de teste/CI)."""
    cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET]
    if csv_fallback and os.path.exists(csv_fallback):
        df = pd.read_csv(csv_fallback)
        return df[[c for c in cols if c in df.columns]].dropna()

    query = f"select {', '.join(cols)} from marts.fct_delivery_performance"
    df = pd.read_sql(query, engine)
    return df.dropna()


def build_pipeline(model):
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def evaluate(y_true, y_pred, y_proba) -> dict:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, y_proba),
    }


def main(csv_fallback: str = None):
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("olist-delivery-delay-prediction")

    engine = None
    try:
        engine = get_engine()
    except Exception:
        pass

    df = load_training_data(engine, csv_fallback=csv_fallback)
    print(f"[info] Dataset de treino: {df.shape[0]:,} linhas, "
          f"taxa de atraso: {df[TARGET].mean():.2%}")

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    candidates = {
        "baseline_logistic_regression": LogisticRegression(max_iter=1000),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42
        ),
    }

    best_model_name, best_f1, best_pipeline = None, -1, None

    # Dataset é desbalanceado (poucos pedidos atrasam) -> compensamos com sample_weight,
    # já que nem todo classificador aceita class_weight="balanced" diretamente (GB não aceita).
    sample_weight = compute_sample_weight("balanced", y_train)

    for name, model in candidates.items():
        with mlflow.start_run(run_name=name):
            pipeline = build_pipeline(model)
            pipeline.fit(X_train, y_train, model__sample_weight=sample_weight)

            y_pred = pipeline.predict(X_test)
            y_proba = pipeline.predict_proba(X_test)[:, 1]
            metrics = evaluate(y_test, y_pred, y_proba)

            mlflow.log_param("model_type", name)
            mlflow.log_params(model.get_params())
            mlflow.log_metrics(metrics)
            mlflow.sklearn.log_model(pipeline, artifact_path="model")

            print(f"[{name}] AUC={metrics['roc_auc']:.4f} "
                  f"F1={metrics['f1']:.4f} Recall={metrics['recall']:.4f}")

            # Selecionamos pelo F1, não pela AUC: com ~8% de positivos, AUC alta pode
            # esconder um modelo que quase nunca prevê atraso (ver model_card.md).
            if metrics["f1"] > best_f1:
                best_f1 = metrics["f1"]
                best_model_name = name
                best_pipeline = pipeline

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    model_path = os.path.join(ARTIFACT_DIR, "model.pkl")
    joblib.dump(best_pipeline, model_path)
    print(f"[done] Melhor modelo: {best_model_name} (F1={best_f1:.4f}) salvo em {model_path}")

    # também salva uma amostra de referência para o monitoramento de drift
    X_train.assign(**{TARGET: y_train.values}).to_csv(
        os.path.join(ARTIFACT_DIR, "reference_data.csv"), index=False
    )


if __name__ == "__main__":
    import sys
    fallback = sys.argv[1] if len(sys.argv) > 1 else None
    main(csv_fallback=fallback)
