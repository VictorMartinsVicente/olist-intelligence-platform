FROM python:3.11-slim

WORKDIR /app

COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY ml/artifacts/model.pkl ./ml/artifacts/model.pkl

ENV MODEL_PATH=/app/ml/artifacts/model.pkl

EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
