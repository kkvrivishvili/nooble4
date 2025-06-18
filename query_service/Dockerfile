# Usa una imagen base de Python
FROM python:3.11-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos de requerimientos
COPY requirements.txt requirements.txt

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código de la aplicación
COPY ./query_service /app/query_service

# Copia el módulo común (asumiendo que está en el directorio padre)
# En un entorno real, esto podría manejarse como un paquete instalable
COPY ../common /app/common

# Variables de entorno por defecto
ENV PYTHONPATH=/app
ENV QUERY_SERVICE_NAME=query
ENV QUERY_ENVIRONMENT=development
ENV QUERY_LOG_LEVEL=INFO

# Puerto por defecto
EXPOSE 8002

# Comando de inicio
CMD ["python", "-m", "query_service.main"]
