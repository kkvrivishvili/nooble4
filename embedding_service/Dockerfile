FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requirements
COPY .env .
COPY embedding_service/requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación, preservando la estructura de directorios
COPY embedding_service/ /app/embedding_service/

# Copiar módulo common (asumiendo estructura de monorepo)
COPY common/ /app/common/

# Variables de entorno por defecto
ENV PYTHONPATH=/app
ENV EMBEDDING_SERVICE_NAME=embedding
ENV EMBEDDING_ENVIRONMENT=development
ENV EMBEDDING_LOG_LEVEL=INFO

# Puerto por defecto
EXPOSE 8006

# Comando de inicio
CMD ["python", "-m", "embedding_service.main"]