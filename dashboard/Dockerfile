FROM python:3.11-slim

WORKDIR /app

COPY dashboard/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard/ ./dashboard/

EXPOSE 8501
CMD ["sh", "-c", "streamlit run dashboard/app.py --server.address=0.0.0.0 --server.port=${PORT:-8501}"]
