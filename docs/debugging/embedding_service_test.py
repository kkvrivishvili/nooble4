"""
Script de prueba para verificar que el Embedding Service funciona correctamente.
"""

# Agregar directorio principal al path
import sys
import os
sys.path.append(os.path.abspath("."))

# Importar módulos del servicio
from embedding_service.config.settings import get_settings
from embedding_service.services.validation_service import ValidationService
from embedding_service.services.embedding_processor import EmbeddingProcessor
from embedding_service.workers.embedding_worker import EmbeddingWorker
from common.models.execution_context import create_agent_context

# Verificar settings
print("=== TEST DE CONFIGURACIÓN ===")
settings = get_settings()
print(f"Servicio: {settings.service_name}")
print(f"Domain name: {settings.domain_name}")
print(f"Tracking habilitado: {settings.enable_embedding_tracking}")
print(f"Cache TTL: {settings.embedding_cache_ttl}")

# Verificar tier_limits
print("\n=== TEST DE LÍMITES POR TIER ===")
for tier in ["free", "basic", "professional", "enterprise"]:
    limits = settings.get_tier_limits(tier)
    print(f"Tier {tier}: {limits['max_texts_per_request']} textos, {limits['max_text_length']} chars")

# Crear contexto de ejecución
print("\n=== TEST DE CONTEXTO ===\n")
context = create_agent_context(
    agent_id="test-agent-123",
    tenant_id="test_tenant", 
    tenant_tier="basic",
    collection_id="test-collection-456"
)
print(f"Contexto creado: {context.tenant_id} ({context.tenant_tier})")

# Verificar ValidationService
print("\n=== TEST DE VALIDATION SERVICE ===")
validation_service = ValidationService()
print("ValidationService inicializado correctamente")

# Verificar EmbeddingProcessor
print("\n=== TEST DE EMBEDDING PROCESSOR ===")
embedding_processor = EmbeddingProcessor(validation_service)
print("EmbeddingProcessor inicializado correctamente")

# Verificar EmbeddingWorker
print("\n=== TEST DE EMBEDDING WORKER ===")
worker = EmbeddingWorker()
print(f"Worker inicializado para dominio: {worker.domain}")

print("\n¡TEST COMPLETADO CON ÉXITO!")
