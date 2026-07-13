FROM python:3.11-slim

WORKDIR /srv/metadata-api

# System deps for psycopg2-binary wheels are not required (binary wheel),
# but keep build tools available for platforms without prebuilt wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

ENV METADATA_DATABASE_URL="postgresql+psycopg2://quarry_admin:quarry_dev_password@postgres:5432/quarry_metadata"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
