FROM python:3.10-slim
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "vault_guard.api:app", "--host", "0.0.0.0", "--port", "8000"]
