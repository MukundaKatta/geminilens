FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GEMINILENS_TRACES=/data/traces.jsonl

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY app ./app
COPY examples ./examples
COPY README.md LICENSE ./

RUN pip install . \
 && pip install streamlit pandas httpx pydantic google-genai

RUN mkdir -p /data && chmod 777 /data

EXPOSE 8080

# Cloud Run sets PORT; Streamlit needs --server.port to match.
CMD streamlit run app/dashboard.py \
    --server.port "${PORT:-8080}" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
