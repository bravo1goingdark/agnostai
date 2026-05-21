FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system agnost \
    && useradd --system --gid agnost --home-dir /app agnost

COPY pyproject.toml README.md ./
COPY app ./app

ARG PACKAGE_EXTRAS=""
RUN pip install --upgrade pip \
    && pip install ".${PACKAGE_EXTRAS}"

USER agnost

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
