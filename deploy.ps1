# Script de despliegue para PowerShell

Write-Host "Iniciando despliegue de Nooble4..." -ForegroundColor Cyan

# Verificar que existe el archivo .env
if (-not (Test-Path .env)) {
    Write-Host "Error: No se encontro el archivo .env" -ForegroundColor Red
    exit 1
}

# Limpiar contenedores anteriores
Write-Host "Limpiando contenedores anteriores..." -ForegroundColor Yellow
docker-compose down -v

# Construir imagenes
Write-Host "Construyendo imagenes..." -ForegroundColor Yellow
docker-compose build

# Iniciar bases de datos primero
Write-Host "Iniciando bases de datos..." -ForegroundColor Yellow
docker-compose up -d postgres_database redis_database qdrant_database

# Esperar a que PostgreSQL este listo
Write-Host "Esperando a que PostgreSQL este listo..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Ejecutar migraciones de Kong
Write-Host "Ejecutando migraciones de Kong..." -ForegroundColor Yellow
docker-compose run --rm kong-migrations

# Iniciar servicios de infraestructura
Write-Host "Iniciando servicios de infraestructura..." -ForegroundColor Yellow
docker-compose up -d keycloak kong pgadmin

# Esperar a que los servicios esten listos
Write-Host "Esperando a que los servicios de infraestructura esten listos..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Iniciar microservicios
Write-Host "Iniciando microservicios..." -ForegroundColor Yellow
docker-compose up -d query_service ingestion_service embedding_service agent_execution_service

# Verificar estado de los servicios
Write-Host "Verificando estado de los servicios..." -ForegroundColor Green
docker-compose ps

Write-Host "Despliegue completado!" -ForegroundColor Green
Write-Host ""
Write-Host "URLs de acceso:" -ForegroundColor Cyan
Write-Host "   - Kong Gateway: http://localhost:8081"
Write-Host "   - Kong Admin API: http://localhost:8011"
Write-Host "   - Keycloak: http://localhost:8080"
Write-Host "   - PgAdmin: http://localhost:5050"
Write-Host "   - Query Service: http://localhost:8000"
Write-Host "   - Ingestion Service: http://localhost:8002"
Write-Host "   - Embedding Service: http://localhost:8006"
Write-Host "   - Agent Execution Service: http://localhost:8005"
