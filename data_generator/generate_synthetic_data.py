"""
Gera dados sintéticos no MESMO schema do dataset real "Olist Brazilian E-Commerce"
(https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).

Por que isso existe: para rodar o pipeline de ponta a ponta sem depender de download
manual. Para usar os dados REAIS do Kaggle, basta baixar o dataset, colocar os CSVs
originais em data/raw/ com os mesmos nomes de arquivo, e pular este script.

Uso:
    python data_generator/generate_synthetic_data.py --n-orders 50000
"""
import argparse
import random
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

BR_STATES = [
    "SP", "RJ", "MG", "RS", "PR", "SC", "BA", "GO", "PE", "CE",
    "PA", "MA", "ES", "DF", "AM", "MT", "MS", "PB", "RN", "AL",
]

# Estados mais distantes de SP (onde fica a maior concentração de vendedores) tendem
# a ter prazos maiores e mais variância -> isso cria sinal real para o modelo aprender
STATE_DISTANCE_FACTOR = {
    "SP": 1.0, "RJ": 1.1, "MG": 1.15, "PR": 1.2, "SC": 1.25, "RS": 1.3,
    "GO": 1.3, "DF": 1.3, "ES": 1.2, "BA": 1.5, "PE": 1.7, "CE": 1.8,
    "PA": 2.0, "MA": 2.0, "AM": 2.4, "MT": 1.6, "MS": 1.5, "PB": 1.75,
    "RN": 1.8, "AL": 1.75,
}

PRODUCT_CATEGORIES = [
    "cama_mesa_banho", "beleza_saude", "esporte_lazer", "moveis_decoracao",
    "informatica_acessorios", "utilidades_domesticas", "relogios_presentes",
    "telefonia", "automotivo", "brinquedos", "cool_stuff", "eletronicos",
    "papelaria", "moveis_escritorio", "moda_bolsas_acessorios",
]

PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]


def _rand_id():
    return uuid.uuid4().hex


def generate(n_orders: int, seed: int = 42):
    rng = np.random.default_rng(seed)
    random.seed(seed)

    n_customers = int(n_orders * 0.85)
    n_sellers = max(200, int(n_orders * 0.02))
    n_products = max(500, int(n_orders * 0.05))

    # ---- customers ----
    customers = pd.DataFrame({
        "customer_id": [_rand_id() for _ in range(n_customers)],
        "customer_unique_id": [_rand_id() for _ in range(n_customers)],
        "customer_zip_code_prefix": rng.integers(1000, 99999, n_customers),
        "customer_city": [f"city_{i % 500}" for i in range(n_customers)],
        "customer_state": rng.choice(BR_STATES, n_customers, p=_state_weights()),
    })

    # ---- sellers ----
    sellers = pd.DataFrame({
        "seller_id": [_rand_id() for _ in range(n_sellers)],
        "seller_zip_code_prefix": rng.integers(1000, 99999, n_sellers),
        "seller_city": [f"city_{i % 200}" for i in range(n_sellers)],
        "seller_state": rng.choice(BR_STATES, n_sellers, p=_state_weights(seller=True)),
    })

    # ---- products ----
    products = pd.DataFrame({
        "product_id": [_rand_id() for _ in range(n_products)],
        "product_category_name": rng.choice(PRODUCT_CATEGORIES, n_products),
        "product_weight_g": rng.integers(100, 20000, n_products),
        "product_length_cm": rng.integers(10, 100, n_products),
        "product_height_cm": rng.integers(5, 80, n_products),
        "product_width_cm": rng.integers(5, 80, n_products),
    })

    # ---- orders (o coração do dataset) ----
    start_date = datetime(2016, 9, 1)
    order_ids = [_rand_id() for _ in range(n_orders)]
    customer_ids = rng.choice(customers["customer_id"], n_orders)
    order_purchase_ts = [
        start_date + timedelta(days=int(rng.integers(0, 730)), hours=int(rng.integers(0, 24)))
        for _ in range(n_orders)
    ]

    order_customer_state = customers.set_index("customer_id").loc[customer_ids, "customer_state"].values

    orders_rows = []
    order_items_rows = []
    payments_rows = []
    reviews_rows = []

    for i in range(n_orders):
        oid = order_ids[i]
        purchase_ts = order_purchase_ts[i]
        cust_state = order_customer_state[i]
        distance_factor = STATE_DISTANCE_FACTOR.get(cust_state, 1.5)

        # prazo estimado: baseado na distância, com ruído
        estimated_days = int(max(3, rng.normal(9 * distance_factor, 3)))
        estimated_delivery = purchase_ts + timedelta(days=estimated_days)

        approved_at = purchase_ts + timedelta(hours=int(rng.integers(1, 48)))
        carrier_date = approved_at + timedelta(days=int(rng.integers(0, 3)))

        # tempo real de entrega: correlacionado com distância + ruído + leve chance de atraso maior
        base_delivery_days = rng.normal(8 * distance_factor, 4 * distance_factor)
        delay_shock = rng.choice([0, 0, 0, 1, 1, 2, 4], p=[0.55, 0.15, 0.1, 0.08, 0.06, 0.04, 0.02])
        actual_days = max(1, base_delivery_days + delay_shock)
        delivered_customer_date = purchase_ts + timedelta(days=float(actual_days))

        # 3% dos pedidos nunca chegam a ser entregues (ainda em trânsito / cancelados)
        status = "delivered" if rng.random() > 0.03 else rng.choice(["shipped", "canceled", "processing"])

        orders_rows.append({
            "order_id": oid,
            "customer_id": customer_ids[i],
            "order_status": status,
            "order_purchase_timestamp": purchase_ts,
            "order_approved_at": approved_at,
            "order_delivered_carrier_date": carrier_date,
            "order_delivered_customer_date": delivered_customer_date if status == "delivered" else pd.NaT,
            "order_estimated_delivery_date": estimated_delivery,
        })

        # 1 a 3 itens por pedido
        n_items = rng.choice([1, 1, 2, 2, 3], p=[0.5, 0.2, 0.15, 0.1, 0.05])
        chosen_products = rng.choice(products["product_id"], n_items)
        chosen_sellers = rng.choice(sellers["seller_id"], n_items)
        for item_idx in range(n_items):
            price = float(rng.gamma(3.0, 40.0))
            freight = float(max(5, price * rng.uniform(0.05, 0.25)))
            order_items_rows.append({
                "order_id": oid,
                "order_item_id": item_idx + 1,
                "product_id": chosen_products[item_idx],
                "seller_id": chosen_sellers[item_idx],
                "price": round(price, 2),
                "freight_value": round(freight, 2),
            })

        # pagamento
        payments_rows.append({
            "order_id": oid,
            "payment_type": rng.choice(PAYMENT_TYPES, p=[0.75, 0.18, 0.04, 0.03]),
            "payment_installments": int(rng.choice(range(1, 13))),
            "payment_value": round(sum(r["price"] + r["freight_value"] for r in order_items_rows[-n_items:]), 2),
        })

        # review: nota inversamente relacionada ao atraso real vs estimado
        if status == "delivered":
            delay_days = (delivered_customer_date - estimated_delivery).days
            base_score = 4.3 - max(0, delay_days) * 0.35 + rng.normal(0, 0.6)
            score = int(np.clip(round(base_score), 1, 5))
            reviews_rows.append({
                "order_id": oid,
                "review_id": _rand_id(),
                "review_score": score,
                "review_creation_date": delivered_customer_date + timedelta(days=int(rng.integers(1, 10))),
            })

    orders = pd.DataFrame(orders_rows)
    order_items = pd.DataFrame(order_items_rows)
    payments = pd.DataFrame(payments_rows)
    reviews = pd.DataFrame(reviews_rows)

    return {
        "olist_customers_dataset": customers,
        "olist_sellers_dataset": sellers,
        "olist_products_dataset": products,
        "olist_orders_dataset": orders,
        "olist_order_items_dataset": order_items,
        "olist_order_payments_dataset": payments,
        "olist_order_reviews_dataset": reviews,
    }


def _state_weights(seller: bool = False):
    """SP concentra a maior parte de clientes/vendedores, como no dataset real."""
    weights = np.array([
        0.42 if s == "SP" else (0.13 if s == "RJ" else (0.11 if s == "MG" else 1.0))
        for s in BR_STATES
    ])
    if seller:
        weights = np.array([
            0.55 if s == "SP" else (0.10 if s == "RJ" else (0.08 if s == "MG" else 0.5))
            for s in BR_STATES
        ])
    return weights / weights.sum()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-orders", type=int, default=50000)
    parser.add_argument("--out-dir", type=str, default="data/raw")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    tables = generate(args.n_orders, args.seed)
    import os
    os.makedirs(args.out_dir, exist_ok=True)
    for name, df in tables.items():
        path = f"{args.out_dir}/{name}.csv"
        df.to_csv(path, index=False)
        print(f"[ok] {path} ({len(df):,} linhas)")


if __name__ == "__main__":
    main()
