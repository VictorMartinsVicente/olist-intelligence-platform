FROM python:3.11-slim

WORKDIR /app

COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY ml/train.py ./ml/train.py
COPY ml/data/training_snapshot.csv.gz ./ml/data/training_snapshot.csv.gz

# O modelo e treinado durante o build. Por padrao usa o snapshot com o dataset
# REAL da Olist (ml/data/training_snapshot.csv.gz, gerado por
# dashboard/build_snapshot.py com a mesma logica do dbt). Para treinar direto
# contra o Postgres (Neon), passe TRAINING_DATA="" como build arg; as credenciais
# vem das variaveis de ambiente do servico no Render (repassadas como build args).
ARG TRAINING_DATA=ml/data/training_snapshot.csv.gz
ARG POSTGRES_HOST
ARG POSTGRES_PORT
ARG POSTGRES_DB
ARG POSTGRES_USER
ARG POSTGRES_PASSWORD

RUN POSTGRES_HOST=$POSTGRES_HOST \
    POSTGRES_PORT=$POSTGRES_PORT \
    POSTGRES_DB=$POSTGRES_DB \
    POSTGRES_USER=$POSTGRES_USER \
    POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
    MLFLOW_TRACKING_URI=file:///tmp/mlruns \
    python ml/train.py $TRAINING_DATA

ENV MODEL_PATH=/app/ml/artifacts/model.pkl

EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
