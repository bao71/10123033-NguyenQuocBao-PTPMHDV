FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
       > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip \
    for package in API BLL DAL Model Core CLI; do \
        mkdir "$package" && touch "$package/__init__.py"; \
    done \
    && pip install ".[test]" \
    && rm -rf API BLL DAL Model Core CLI

COPY API ./API
COPY BLL ./BLL
COPY DAL ./DAL
COPY Model ./Model
COPY Core ./Core
COPY CLI ./CLI
COPY Tests ./Tests
COPY Frontend ./Frontend
RUN useradd --create-home --uid 10001 clinic \
    && chown -R clinic:clinic /app

USER clinic
EXPOSE 8000
CMD ["uvicorn", "API.main:app", "--host", "0.0.0.0", "--port", "8000"]
