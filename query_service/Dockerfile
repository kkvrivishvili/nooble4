FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requirements
COPY .env .
COPY query_service/requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación, preservando la estructura de directorios
COPY query_service/ /app/query_service/

# Copiar módulo common (asumiendo estructura de monorepo)
COPY common/ /app/common/

# Variables de entorno por defecto
ENV PYTHONPATH=/app
ENV QUERY_SERVICE_NAME=query
ENV QUERY_ENVIRONMENT=development
ENV QUERY_LOG_LEVEL=INFO

# Puerto por defecto
EXPOSE 8000

# Comando de inicio
CMD ["python", "-m", "query_service.main"]