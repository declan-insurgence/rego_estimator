FROM node:20-alpine AS ui-build
WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm install
COPY ui/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY server/pyproject.toml /app/server/pyproject.toml
RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx beautifulsoup4 pydantic pydantic-settings azure-storage-blob pdfplumber
COPY server/src /app/server/src
COPY --from=ui-build /app/server/src/vic_rego_estimator/static/widget /app/server/src/vic_rego_estimator/static/widget
ENV PYTHONPATH=/app/server/src
EXPOSE 8080
CMD ["python", "-m", "vic_rego_estimator.main"]
