# DevSynapse AI - container build

FROM python:3.13-slim AS python-builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -c requirements.lock


FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN npm run build


FROM nginx:alpine AS nginx-proxy

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist


FROM python:3.13-slim AS production

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r devsynapse && \
    useradd -r -g devsynapse -m -d /home/devsynapse devsynapse

WORKDIR /app

COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY api ./api
COPY config ./config
COPY core ./core
COPY plugins ./plugins
COPY scripts ./scripts
COPY .env.example LICENSE README.md ./
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN mkdir -p /var/lib/devsynapse-ai && \
    chown -R devsynapse:devsynapse /app /var/lib/devsynapse-ai

USER devsynapse

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV DEVSYNAPSE_HOME=/var/lib/devsynapse-ai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]


FROM production AS development

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dev.txt requirements-dev.lock ./
RUN pip install --no-cache-dir -r requirements-dev.txt -c requirements-dev.lock

USER devsynapse

CMD ["python", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


FROM production AS default
