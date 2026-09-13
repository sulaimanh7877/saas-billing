FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml readme.md LICENSE ./
COPY src ./src

RUN python -m pip install --upgrade pip && python -m pip install .

EXPOSE 8000

CMD ["uvicorn", "billing_engine.server:create_server", "--factory", "--host", "0.0.0.0", "--port", "8000"]
