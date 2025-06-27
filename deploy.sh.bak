#!/bin/bash

echo "🚀 Iniciando despliegue de Nooble4..."

# Verificar que existe el archivo .env
if [ ! -f .env ]; then
    echo "❌ Error: No se encontró el archivo .env"
    exit 1
fi

# Limpiar contenedores anteriores
echo "🧹 Limpiando contenedores anteriores..."
docker-compose down -v

# Construir imágenes
echo "🔨 Construyendo imágenes..."
docker-compose build

# Iniciar bases de datos primero
echo "🗄️ Iniciando bases de datos..."
docker-compose up -d postgres_database redis_database qdrant_database

# Esperar a que PostgreSQL esté listo
echo "⏳ Esperando a que PostgreSQL esté listo..."
sleep 10

# Ejecutar migraciones de Kong
echo "🔄 Ejecutando migraciones de Kong..."
docker-compose run --rm kong-migrations

# Iniciar servicios de infraestructura
echo "🏗️ Iniciando servicios de infraestructura..."
docker-compose up -d keycloak kong pgadmin

# Esperar a que los servicios estén listos
echo "⏳ Esperando a que los servicios de infraestructura estén listos..."
sleep 15

# Iniciar microservicios
echo "🚀 Iniciando microservicios..."
docker-compose up -d query_service ingestion_service embedding_service agent_execution_service

# Verificar estado de los servicios
echo "✅ Verificando estado de los servicios..."
docker-compose ps

echo "✨ Despliegue completado!"
echo ""
echo "📌 URLs de acceso:"
echo "   - Kong Gateway: http://localhost:8081"
echo "   - Kong Admin API: http://localhost:8011"
echo "   - Keycloak: http://localhost:8080"
echo "   - PgAdmin: http://localhost:5050"
echo "   - Query Service: http://localhost:8000"
echo "   - Ingestion Service: http://localhost:8002"
echo "   - Embedding Service: http://localhost:8006"
echo "   - Agent Execution Service: http://localhost:8005"