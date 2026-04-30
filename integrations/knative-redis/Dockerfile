FROM python:3.12-slim

WORKDIR /app

COPY integrations/knative-redis/app.py /app/app.py
COPY integrations/knative-redis/benchmark.py /app/benchmark.py

RUN pip install --no-cache-dir "redis>=5.0.0,<6"

ENV PORT=8080

EXPOSE 8080

ENTRYPOINT ["python", "/app/app.py"]
