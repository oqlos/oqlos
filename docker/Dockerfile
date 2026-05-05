FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
COPY oqlos.yaml .
COPY oqlos/ oqlos/

RUN pip install --no-cache-dir -e .

EXPOSE 8200
CMD ["oqlos-server", "--host", "0.0.0.0", "--port", "8200"]
