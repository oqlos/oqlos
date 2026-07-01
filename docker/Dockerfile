FROM node:20-alpine AS ui-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/vendor ./vendor
RUN npm run build

FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
COPY oqlos.yaml .
COPY oqlos/ oqlos/
COPY --from=ui-build /frontend/dist frontend/dist

RUN pip install --no-cache-dir -e .

EXPOSE 8200
CMD ["oqlos-server", "--host", "0.0.0.0", "--port", "8200"]
