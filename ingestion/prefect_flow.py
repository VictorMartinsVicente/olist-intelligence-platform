"""
Orquestra o pipeline completo: ingestão de dados -> dbt run -> dbt test -> re-treino do modelo.

Rodar uma vez:
    python ingestion/prefect_flow.py

Agendar para rodar semanalmente (ex: toda segunda às 6h):
    prefect deployment build ingestion/prefect_flow.py:olist_pipeline \
        --name weekly-refresh --cron "0 6 * * 1"
    prefect deployment apply olist_pipeline-deployment.yaml
"""
import subprocess

from prefect import flow, task

from ingestion.load_raw_to_postgres import get_engine, load_all


@task(retries=2, retry_delay_seconds=30, log_prints=True)
def ingest_raw_data():
    engine = get_engine()
    load_all(engine)
    return True


@task(retries=1, log_prints=True)
def run_dbt(command: str):
    """Executa um comando dbt (run ou test) no diretório transformation/."""
    result = subprocess.run(
        ["dbt", command, "--project-dir", "transformation", "--profiles-dir", "transformation"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"dbt {command} falhou (código {result.returncode})")
    return result.returncode


@task(retries=1, log_prints=True)
def retrain_model():
    from ml.train import main as train_main
    train_main()


@flow(name="olist-data-and-ml-pipeline", log_prints=True)
def olist_pipeline():
    print("[1/4] Ingerindo dados raw para Postgres...")
    ingest_raw_data()

    print("[2/4] Rodando transformações dbt (staging -> intermediate -> marts)...")
    run_dbt("run")

    print("[3/4] Validando qualidade dos dados (dbt test)...")
    run_dbt("test")

    print("[4/4] Re-treinando o modelo de previsão de atraso...")
    retrain_model()

    print("[done] Pipeline completo executado com sucesso.")


if __name__ == "__main__":
    olist_pipeline()
