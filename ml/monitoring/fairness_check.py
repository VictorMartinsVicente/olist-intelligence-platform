"""
Verifica se o modelo tem performance consistente entre diferentes estados do cliente
(checagem de fairness/robustez geografica) - a etapa de "Model Evaluation" que o
CRISP-ML(Q) adiciona em cima do CRISP-DM tradicional, e que o model_card.md ja citava
como limitacao qualitativa (viés geografico esperado em regioes com menos dados).

Reconstroi o MESMO split de treino/teste usado em train.py (random_state=42), entao
os resultados aqui sao diretamente comparaveis as metricas reportadas no model_card.

Uso:
    python ml/monitoring/fairness_check.py
"""
import os

import joblib
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
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

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "artifacts", "model.pkl")

# Abaixo desse recall, o estado e sinalizado como "sub-atendido" pelo modelo
RECALL_ALERT_THRESHOLD_RATIO = 0.7  # 70% do recall global
MIN_ROWS_PER_STATE = 30  # estados com poucas amostras no teste sao ignorados (ruido)


def get_engine():
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "olist")
    user = os.environ.get("POSTGRES_USER", "olist_user")
    password = os.environ.get("POSTGRES_PASSWORD", "olist_pass")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}")


def load_data(engine=None, csv_fallback: str = None) -> pd.DataFrame:
    cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET]
    if csv_fallback and os.path.exists(csv_fallback):
        df = pd.read_csv(csv_fallback)
        return df[[c for c in cols if c in df.columns]].dropna()
    query = f"select {', '.join(cols)} from marts.fct_delivery_performance"
    return pd.read_sql(query, engine).dropna()


def main(csv_fallback: str = None):
    if not os.path.exists(MODEL_PATH):
        raise SystemExit(f"Modelo nao encontrado em {MODEL_PATH}. Rode ml/train.py primeiro.")

    model = joblib.load(MODEL_PATH)

    engine = None
    try:
        engine = get_engine()
    except Exception:
        pass
    df = load_data(engine, csv_fallback=csv_fallback)

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET]
    # Mesma seed e split de train.py -> reconstroi o held-out test set exato
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    y_pred = model.predict(X_test)

    overall_recall = recall_score(y_test, y_pred, zero_division=0)
    overall_precision = precision_score(y_test, y_pred, zero_division=0)
    overall_f1 = f1_score(y_test, y_pred, zero_division=0)

    print(f"[global] recall={overall_recall:.3f} precision={overall_precision:.3f} f1={overall_f1:.3f} "
          f"(n={len(y_test)})")
    print()

    results = []
    for state in sorted(X_test["customer_state"].unique()):
        mask = X_test["customer_state"] == state
        n = int(mask.sum())
        if n < MIN_ROWS_PER_STATE:
            continue
        r = recall_score(y_test[mask], y_pred[mask], zero_division=0)
        p = precision_score(y_test[mask], y_pred[mask], zero_division=0)
        results.append({"state": state, "n": n, "recall": r, "precision": p})

    results_df = pd.DataFrame(results).sort_values("recall")
    pd.set_option("display.float_format", lambda x: f"{x:.3f}")
    print(results_df.to_string(index=False))

    alert_threshold = overall_recall * RECALL_ALERT_THRESHOLD_RATIO
    flagged = results_df[results_df["recall"] < alert_threshold]

    print()
    if len(flagged) > 0:
        print(f"[alerta] {len(flagged)} estado(s) com recall abaixo de "
              f"{RECALL_ALERT_THRESHOLD_RATIO:.0%} do recall global "
              f"({alert_threshold:.3f}):")
        print(flagged[["state", "n", "recall"]].to_string(index=False))
        print()
        print("Isso NAO significa que o modelo esta quebrado -- e esperado em estados")
        print("com poucos dados de treino (ver model_card.md, secao 'Vies geografico').")
        print("Serve como sinal para priorizar coleta de mais dados nessas regioes")
        print("antes de usar o modelo para decisoes automaticas la.")
    else:
        print("[ok] Nenhum estado com recall desproporcionalmente abaixo do global.")


if __name__ == "__main__":
    import sys
    fallback = sys.argv[1] if len(sys.argv) > 1 else None
    main(csv_fallback=fallback)
