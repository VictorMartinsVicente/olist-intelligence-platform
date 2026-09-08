FROM python:3.11-slim

WORKDIR /app

COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY ml/train.py ./ml/train.py

# O modelo e treinado durante o build, direto contra o Postgres (Neon),
# usando as credenciais passadas como variaveis de ambiente do servico no Render
# (Render as repassa automaticamente como build args para servicos Docker).
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
    python ml/train.py

ENV MODEL_PATH=/app/ml/artifacts/model.pkl

EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
