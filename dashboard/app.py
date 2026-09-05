"""
Dashboard de negócio: KPIs de atraso na entrega, impacto na satisfação do cliente,
e um simulador de risco de atraso usando a API do modelo.

Rodar localmente:
    streamlit run dashboard/app.py
"""
import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(page_title="Olist Intelligence Platform", layout="wide")

def _get_config(key: str, default: str = None) -> str:
    """Lê configuração de st.secrets (Streamlit Cloud) com fallback para variável
    de ambiente (Docker/local). Isso permite rodar o mesmo código nos dois lugares."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


@st.cache_resource
def get_engine():
    host = _get_config("POSTGRES_HOST", "localhost")
    port = _get_config("POSTGRES_PORT", "5432")
    db = _get_config("POSTGRES_DB", "olist")
    user = _get_config("POSTGRES_USER", "olist_user")
    password = _get_config("POSTGRES_PASSWORD", "olist_pass")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}")


@st.cache_data(ttl=600)
def load_delivery_data() -> pd.DataFrame:
    engine = get_engine()
    query = "select * from marts.fct_delivery_performance"
    return pd.read_sql(query, engine)


@st.cache_data(ttl=600)
def load_seller_data() -> pd.DataFrame:
    engine = get_engine()
    query = "select * from marts.fct_seller_performance"
    return pd.read_sql(query, engine)


def render_kpis(df: pd.DataFrame):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de pedidos entregues", f"{len(df):,}")
    col2.metric("Taxa de atraso", f"{df['is_delayed'].mean():.1%}")
    col3.metric("Nota média de review", f"{df['review_score'].mean():.2f} / 5")
    delayed_review = df.loc[df.is_delayed == 1, "review_score"].mean()
    ontime_review = df.loc[df.is_delayed == 0, "review_score"].mean()
    col4.metric(
        "Impacto do atraso na nota",
        f"{delayed_review:.2f} vs {ontime_review:.2f}",
        delta=f"{delayed_review - ontime_review:+.2f}",
        delta_color="inverse",
    )


def render_delay_impact_chart(df: pd.DataFrame):
    st.subheader("Atraso na entrega vs. satisfação do cliente")
    order = ["entregue_adiantado", "no_prazo", "atraso_leve", "atraso_grave"]
    grouped = (
        df.groupby("delay_bucket")["review_score"]
        .mean()
        .reindex(order)
        .reset_index()
    )
    fig = px.bar(
        grouped, x="delay_bucket", y="review_score",
        labels={"delay_bucket": "Situação da entrega", "review_score": "Nota média de review"},
        color="review_score", color_continuous_scale="RdYlGn",
        range_color=[1, 5],
    )
    st.plotly_chart(fig, use_container_width=True)


def render_delay_by_state_chart(df: pd.DataFrame):
    st.subheader("Taxa de atraso por estado do cliente")
    by_state = (
        df.groupby("customer_state")
        .agg(taxa_atraso=("is_delayed", "mean"), total_pedidos=("order_id", "count"))
        .query("total_pedidos >= 20")
        .sort_values("taxa_atraso", ascending=False)
        .reset_index()
    )
    fig = px.bar(
        by_state, x="customer_state", y="taxa_atraso",
        labels={"customer_state": "Estado", "taxa_atraso": "Taxa de atraso"},
        hover_data=["total_pedidos"],
    )
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)


def render_top_sellers(df_sellers: pd.DataFrame):
    st.subheader("Top 10 vendedores por receita")
    top = df_sellers.sort_values("total_revenue", ascending=False).head(10)
    fig = px.bar(
        top, x="total_revenue", y="seller_id", orientation="h",
        labels={"total_revenue": "Receita total", "seller_id": "Vendedor"},
        color="seller_state",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)


def render_delay_simulator():
    st.subheader("🔮 Simulador de risco de atraso")
    st.caption("Testa a API do modelo de ML com dados hipotéticos de um novo pedido")

    with st.form("simulator"):
        c1, c2, c3 = st.columns(3)
        estimated_days = c1.slider("Prazo estimado (dias)", 1, 60, 15)
        order_value = c2.number_input("Valor do pedido (R$)", min_value=1.0, value=150.0)
        freight_value = c3.number_input("Valor do frete (R$)", min_value=1.0, value=25.0)

        c4, c5, c6 = st.columns(3)
        n_items = c4.number_input("Número de itens", min_value=1, value=1, step=1)
        installments = c5.number_input("Parcelas", min_value=1, value=3, step=1)
        month = c6.selectbox("Mês da compra", list(range(1, 13)), index=10)

        c7, c8, c9 = st.columns(3)
        customer_state = c7.selectbox("Estado do cliente", ["SP", "RJ", "MG", "BA", "PA", "AM", "RS"])
        seller_state = c8.selectbox("Estado do vendedor", ["SP", "RJ", "MG", "SC", "PR"])
        category = c9.selectbox(
            "Categoria do produto",
            ["informatica_acessorios", "cama_mesa_banho", "beleza_saude", "moveis_decoracao"],
        )
        payment_type = st.selectbox("Forma de pagamento", ["credit_card", "boleto", "voucher", "debit_card"])

        submitted = st.form_submit_button("Calcular risco de atraso")

    if submitted:
        payload = {
            "estimated_delivery_days": estimated_days,
            "order_total_value": order_value,
            "avg_freight_value": freight_value,
            "n_items": n_items,
            "payment_installments": installments,
            "purchase_month": month,
            "purchase_day_of_week": 3,
            "customer_state": customer_state,
            "primary_seller_state": seller_state,
            "primary_product_category": category,
            "payment_type": payment_type,
        }
        try:
            api_url = _get_config("API_URL", "http://localhost:8000")
            resp = requests.post(f"{api_url}/predict", json=payload, timeout=5)
            resp.raise_for_status()
            result = resp.json()
            risk_color = {"baixo": "green", "medio": "orange", "alto": "red"}[result["risk_level"]]
            st.markdown(
                f"**Probabilidade de atraso:** {result['delay_probability']:.1%}  \n"
                f"**Nível de risco:** :{risk_color}[{result['risk_level'].upper()}]"
            )
        except Exception as e:
            st.error(f"Não foi possível conectar à API do modelo ({api_url}): {e}")


def main():
    st.title("📦 Olist Intelligence Platform")
    st.caption("Pipeline de dados + ML em produção para prever risco de atraso na entrega")

    try:
        df = load_delivery_data()
        df_sellers = load_seller_data()
    except Exception as e:
        st.error(
            "Não foi possível conectar ao Postgres. Confirme que `docker-compose up` está "
            f"rodando e que o dbt já foi executado (`dbt run`). Erro: {e}"
        )
        st.stop()

    render_kpis(df)
    st.divider()

    col_left, col_right = st.columns(2)
    with col_left:
        render_delay_impact_chart(df)
    with col_right:
        render_delay_by_state_chart(df)

    render_top_sellers(df_sellers)
    st.divider()
    render_delay_simulator()


if __name__ == "__main__":
    main()
