"""
Testes de fumaça (smoke tests) para os scripts de monitoramento.

[Framework] CRISP-ML(Q): Monitoring -- garante que fairness_check.py e
drift_report.py continuam executáveis (sem erro) a cada mudança no pipeline.
Não valida a EXATIDÃO das métricas (isso é responsabilidade da análise manual
documentada em ml/model_card.md) -- só que os scripts rodam de ponta a ponta,
em qualquer ambiente, sem depender de alguém ter treinado um modelo antes.

Rodar com: pytest tests/test_monitoring.py -v
"""
import os

import joblib
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from ml.train import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET, build_pipeline

SAMPLE_CSV = os.path.join(
    os.path.dirname(__file__), "..", "analytics", "sample_fct_delivery_performance.csv"
)


@pytest.fixture(scope="module")
def tiny_model_path(tmp_path_factory):
    """Treina um modelo mínimo e rápido só para os testes de monitoramento
    terem algo para carregar -- não usa o dataset completo nem validação
    cruzada, propositalmente, para o teste rodar em segundos."""
    df = pd.read_csv(SAMPLE_CSV).dropna(subset=NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET])
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET]

    pipeline = build_pipeline(LogisticRegression(max_iter=200))
    pipeline.fit(X, y)

    model_path = tmp_path_factory.mktemp("model") / "model.pkl"
    joblib.dump(pipeline, model_path)
    return str(model_path)


def test_fairness_check_runs_end_to_end(tiny_model_path, monkeypatch, capsys):
    from ml.monitoring import fairness_check

    monkeypatch.setattr(fairness_check, "MODEL_PATH", tiny_model_path)
    monkeypatch.setattr(fairness_check, "MIN_ROWS_PER_STATE", 5)  # amostra pequena no teste

    fairness_check.main(csv_fallback=SAMPLE_CSV)

    captured = capsys.readouterr()
    assert "[global]" in captured.out


def test_drift_report_generates_html(tmp_path):
    pytest.importorskip("evidently")
    from ml.monitoring.drift_report import generate_report

    df = pd.read_csv(SAMPLE_CSV)
    half = len(df) // 2
    reference_path = tmp_path / "reference.csv"
    current_path = tmp_path / "current.csv"
    output_path = tmp_path / "drift.html"

    df.iloc[:half].to_csv(reference_path, index=False)
    df.iloc[half:].to_csv(current_path, index=False)

    generate_report(str(reference_path), str(current_path), str(output_path))

    assert output_path.exists()
    assert output_path.stat().st_size > 0
