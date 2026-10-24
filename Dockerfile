# API and worker image. The web app has its own image (web/Dockerfile).
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install ".[llm]"

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FKP_HOME=/app
RUN useradd --uid 10001 --create-home fkp
COPY --from=build /install /usr/local
WORKDIR /app
COPY config ./config
COPY data ./data
COPY migrations ./migrations
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["fkp", "serve", "--port", "8000"]
