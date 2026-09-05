"""
Gera um relatório de data drift comparando os dados de referência (usados no treino)
com dados "novos" (simulando produção), usando a biblioteca Evidently.

Isso é o que separa um projeto de ML "amador" de um pensado pra produção: modelo
degrada com o tempo porque o mundo muda (novo padrão de compra, nova região, etc),
e sem monitoramento você só descobre isso quando já causou dano.

Uso:
    python ml/monitoring/drift_report.py --new-data path/to/new_data.csv
"""
import argparse
import os

import pandas as pd

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")
REFERENCE_PATH = os.path.join(ARTIFACT_DIR, "reference_data.csv")


def generate_report(reference_path: str, new_data_path: str, output_path: str):
    try:
        from evidently.metric_preset import DataDriftPreset
        from evidently.report import Report
    except ImportError:
        raise SystemExit(
            "Instale a dependência: pip install evidently"
        )

    reference = pd.read_csv(reference_path)
    current = pd.read_csv(new_data_path)

    # garante que as duas amostras tenham as mesmas colunas
    common_cols = [c for c in reference.columns if c in current.columns]
    reference = reference[common_cols]
    current = current[common_cols]

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference, current_data=current)
    report.save_html(output_path)
    print(f"[ok] Relatório de drift salvo em {output_path}")

    result = report.as_dict()
    drift_detected = result["metrics"][0]["result"].get("dataset_drift", None)
    if drift_detected is not None:
        status = "DRIFT DETECTADO" if drift_detected else "sem drift significativo"
        print(f"[resultado] {status}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default=REFERENCE_PATH)
    parser.add_argument("--new-data", required=True,
                         help="CSV com dados novos (ex: exportação semanal de produção)")
    parser.add_argument("--output", default=os.path.join(ARTIFACT_DIR, "drift_report.html"))
    args = parser.parse_args()

    generate_report(args.reference, args.new_data, args.output)


if __name__ == "__main__":
    main()
