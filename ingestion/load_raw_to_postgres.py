"""
Carrega os CSVs de data/raw/ para o schema `raw` no Postgres.

Uso:
    python ingestion/load_raw_to_postgres.py

Variáveis de ambiente esperadas (ver .env.example):
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
"""
import glob
import os
import sys

import pandas as pd
from sqlalchemy import create_engine, text

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def get_engine():
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "olist")
    user = os.environ.get("POSTGRES_USER", "olist_user")
    password = os.environ.get("POSTGRES_PASSWORD", "olist_pass")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def load_all(engine, raw_dir: str = RAW_DIR, schema: str = "raw"):
    csv_paths = sorted(glob.glob(os.path.join(raw_dir, "*.csv")))
    if not csv_paths:
        print(f"[erro] Nenhum CSV encontrado em {raw_dir}. Rode o gerador de dados "
              f"(data_generator/generate_synthetic_data.py) ou baixe o dataset real do Kaggle.")
        sys.exit(1)

    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

    for path in csv_paths:
        table_name = os.path.splitext(os.path.basename(path))[0]
        df = pd.read_csv(path)

        # normaliza colunas de data conhecidas para timestamp real (não string)
        for col in df.columns:
            if "date" in col or "timestamp" in col:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        df.to_sql(
            table_name,
            engine,
            schema=schema,
            if_exists="replace",
            index=False,
            method="multi",
            chunksize=5000,
        )
        print(f"[ok] raw.{table_name} carregada ({len(df):,} linhas)")


if __name__ == "__main__":
    engine = get_engine()
    load_all(engine)
    print("[done] Ingestão completa.")
