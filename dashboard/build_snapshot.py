"""
Gera um snapshot compacto dos marts a partir dos CSVs REAIS da Olist (Kaggle),
replicando a mesma logica dos modelos dbt (int_orders_with_delivery_delay ->
int_order_reviews_joined -> fct_delivery_performance / fct_seller_performance).

Por que existe: o dashboard publicado no Streamlit Community Cloud le um banco
Neon que foi populado com dados sinteticos. Este snapshot permite que o
dashboard mostre os numeros reais documentados no README sem depender do banco.

Uso:
    python dashboard/build_snapshot.py --raw-dir data/raw

Fonte dos dados: Brazilian E-Commerce Public Dataset by Olist (Kaggle),
licenca CC BY-NC-SA 4.0.
"""
import argparse
from pathlib import Path

import pandas as pd

OUT_DIR = Path(__file__).parent / "data"
ML_DIR = Path(__file__).parent.parent / "ml" / "data"


def _min_non_null(s: pd.Series):
    """Equivalente ao min() do SQL, que ignora NULL."""
    s = s.dropna()
    return s.min() if len(s) else None


def build(raw_dir: Path) -> None:
    orders = pd.read_csv(
        raw_dir / "olist_orders_dataset.csv",
        parse_dates=[
            "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )
    reviews = pd.read_csv(raw_dir / "olist_order_reviews_dataset.csv")
    customers = pd.read_csv(raw_dir / "olist_customers_dataset.csv")
    items = pd.read_csv(raw_dir / "olist_order_items_dataset.csv")
    sellers = pd.read_csv(raw_dir / "olist_sellers_dataset.csv")

    # int_orders_with_delivery_delay
    orders["order_status"] = orders["order_status"].str.strip().str.lower()
    d = orders[
        (orders.order_status == "delivered")
        & orders.order_delivered_customer_date.notna()
    ].copy()
    d["delay_days"] = (
        d.order_delivered_customer_date - d.order_estimated_delivery_date
    ).dt.total_seconds() / 86400.0
    d["is_delayed"] = (d.delay_days > 0).astype(int)
    d["delay_bucket"] = pd.cut(
        d.delay_days,
        bins=[float("-inf"), -3, 0, 7, float("inf")],
        labels=["entregue_adiantado", "no_prazo", "atraso_leve", "atraso_grave"],
        right=True,
    ).astype(str)
    # bordas iguais ao CASE do dbt: >7 grave, >0 leve, >-3 no_prazo, senao adiantado
    d.loc[d.delay_days <= -3, "delay_bucket"] = "entregue_adiantado"

    # int_order_reviews_joined (inner join, mesmo grao do dbt)
    d = d.merge(reviews[["order_id", "review_score"]], on="order_id", how="inner")

    # fct_delivery_performance (so as colunas que o dashboard usa)
    d = d.merge(customers[["customer_id", "customer_state"]], on="customer_id", how="left")
    delivery = d[
        ["order_id", "customer_state", "delay_days", "is_delayed", "delay_bucket", "review_score"]
    ].copy()
    delivery["delay_days"] = delivery["delay_days"].round(2)

    # fct_seller_performance (Kaggle real nao tem seller_name -> rotulo a partir do id)
    it = items.merge(sellers, on="seller_id", how="left")
    it["item_total_value"] = it.price + it.freight_value
    seller = (
        it.groupby(["seller_id", "seller_state", "seller_city"], dropna=False)
        .agg(
            total_orders=("order_id", "nunique"),
            total_revenue=("item_total_value", "sum"),
            avg_item_price=("price", "mean"),
        )
        .reset_index()
    )
    seller["seller_name"] = (
        "Vendedor " + seller.seller_id.str[:6] + " (" + seller.seller_city.str.title() + ")"
    )

    # features de treino do modelo (mesmas colunas que ml/train.py le do mart)
    payments = pd.read_csv(raw_dir / "olist_order_payments_dataset.csv")
    products = pd.read_csv(raw_dir / "olist_products_dataset.csv")
    it_feat = items.merge(sellers[["seller_id", "seller_state"]], on="seller_id", how="left").merge(
        products[["product_id", "product_category_name"]], on="product_id", how="left"
    )
    it_feat["item_total_value"] = it_feat.price + it_feat.freight_value
    oi = it_feat.groupby("order_id").agg(
        n_items=("order_item_id", "count"),
        order_total_value=("item_total_value", "sum"),
        avg_freight_value=("freight_value", "mean"),
        primary_seller_state=("seller_state", _min_non_null),
        primary_product_category=("product_category_name", _min_non_null),
    )
    # mesmo grao do mart fct_delivery_performance: left join com TODOS os
    # pagamentos (pedidos com mais de um meio de pagamento geram mais de uma linha),
    # para o modelo treinar exatamente sobre o que o dbt entrega
    pay = payments[["order_id", "payment_type", "payment_installments"]].copy()
    pay["payment_type"] = pay.payment_type.str.strip().str.lower()
    train = d.merge(oi, left_on="order_id", right_index=True, how="left").merge(
        pay, on="order_id", how="left"
    )
    train["estimated_delivery_days"] = (
        train.order_estimated_delivery_date - train.order_purchase_timestamp
    ).dt.total_seconds() / 86400.0
    train["purchase_month"] = train.order_purchase_timestamp.dt.month
    # extract(dow) do Postgres: domingo=0 ... sabado=6
    train["purchase_day_of_week"] = (train.order_purchase_timestamp.dt.dayofweek + 1) % 7
    train_cols = [
        "estimated_delivery_days", "order_total_value", "avg_freight_value", "n_items",
        "payment_installments", "purchase_month", "purchase_day_of_week",
        "customer_state", "primary_seller_state", "primary_product_category",
        "payment_type", "is_delayed",
    ]
    train = train[train_cols].dropna().round(2)
    ML_DIR.mkdir(exist_ok=True)
    train.to_csv(ML_DIR / "training_snapshot.csv.gz", index=False)
    print(f"linhas de treino (ml/data/training_snapshot.csv.gz): {len(train):,}")

    OUT_DIR.mkdir(exist_ok=True)
    delivery.to_csv(OUT_DIR / "fct_delivery_performance.csv.gz", index=False)
    seller.round(2).to_csv(OUT_DIR / "fct_seller_performance.csv.gz", index=False)

    print(f"pedidos (orders.csv): {orders.order_id.nunique():,}")
    print(f"linhas fct_delivery_performance: {len(delivery):,}")
    print(f"taxa de atraso: {delivery.is_delayed.mean():.1%}")
    print(
        delivery.groupby("delay_bucket")
        .agg(n=("order_id", "count"), nota=("review_score", "mean"),
             pct_ruim=("review_score", lambda s: (s <= 2).mean()))
        .round(3)
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw", type=Path)
    build(ap.parse_args().raw_dir)
