"""
Testes da lógica de ingestão. Não dependem de um Postgres real rodando —
testam a lógica de transformação de tipos e a validação de arquivos ausentes.

Rodar com: pytest tests/test_ingestion.py -v
"""
import pandas as pd
import pytest

from ingestion.load_raw_to_postgres import load_all


class FakeEngine:
    """Engine falso que só registra o que seria escrito, sem precisar de Postgres."""

    def __init__(self):
        self.written_tables = {}
        self.executed_statements = []

    def begin(self):
        return _FakeConnCtx(self)


class _FakeConnCtx:
    def __init__(self, engine):
        self.engine = engine

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, stmt):
        self.engine.executed_statements.append(str(stmt))


def test_load_all_raises_when_no_csvs(tmp_path):
    engine = FakeEngine()
    empty_dir = tmp_path / "empty_raw"
    empty_dir.mkdir()
    with pytest.raises(SystemExit):
        load_all(engine, raw_dir=str(empty_dir))


def test_date_columns_are_parsed_to_datetime(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    df = pd.DataFrame({
        "order_id": ["a", "b"],
        "order_purchase_timestamp": ["2024-01-01 10:00:00", "2024-01-02 11:00:00"],
    })
    df.to_csv(raw_dir / "olist_orders_dataset.csv", index=False)

    captured = {}

    def fake_to_sql(self, name, engine, schema, if_exists, index, method, chunksize):
        captured["dtype"] = str(self["order_purchase_timestamp"].dtype)

    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql, raising=True)

    engine = FakeEngine()
    load_all(engine, raw_dir=str(raw_dir))

    assert "datetime64" in captured["dtype"]
