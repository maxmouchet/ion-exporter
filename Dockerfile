FROM python:alpine
WORKDIR /app

RUN apk add --no-cache poetry tini
RUN poetry config virtualenvs.in-project true

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN poetry install --no-root --no-dev \
    && rm -rf /root/.cache/*

COPY ion_exporter ion_exporter

ENTRYPOINT ["tini", "--"]
CMD [".venv/bin/python", "-m", "ion_exporter"]
