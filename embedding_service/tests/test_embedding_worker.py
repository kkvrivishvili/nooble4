"""
Pruebas de integración para el EmbeddingWorker.

Estas pruebas verifican que el worker pueda recibir, procesar y responder
a las acciones del dominio 'embedding' a través de Redis.
"""

import asyncio
import json
import pytest
from uuid import uuid4

from common.clients.base_redis_client import BaseRedisClient
from common.models.actions import DomainAction, DomainActionResponse
from embedding_service.workers.embedding_worker import EmbeddingWorker

# Se asume que hay un Redis disponible para las pruebas.
# En un entorno real, se usaría una instancia de prueba o un mock.
REDIS_URL = "redis://localhost:6379/0"

@pytest.fixture(scope="module")
async def redis_client():
    """Fixture para proporcionar un cliente de Redis asíncrono."""
    client = BaseRedisClient(redis_url=REDIS_URL)
    await client.initialize()
    yield client
    await client.close()

@pytest.fixture
async def embedding_worker(redis_client):
    """Fixture para inicializar y ejecutar el EmbeddingWorker en segundo plano."""
    worker = EmbeddingWorker(redis_client=redis_client)
    await worker.initialize()
    
    worker_task = asyncio.create_task(worker.start())
    
    # Dar un pequeño margen para que el worker inicie
    await asyncio.sleep(0.1)
    
    yield worker
    
    # Detener el worker y la tarea
    worker.stop()
    await asyncio.sleep(0.1)
    if not worker_task.done():
        worker_task.cancel()

@pytest.mark.asyncio
async def test_process_embedding_generate_action(redis_client: BaseRedisClient, embedding_worker: EmbeddingWorker):
    """
    Verifica el flujo pseudo-síncrono para la acción 'embedding.generate'.
    """
    correlation_id = str(uuid4())
    callback_queue = embedding_worker.queue_manager.get_queue_name(
        context="responses",
        action_type="embedding.generate",
        correlation_id=correlation_id
    )

    action_payload = {
        "action_type": "embedding.generate",
        "action_id": str(uuid4()),
        "correlation_id": correlation_id,
        "callback_queue_name": callback_queue,
        "data": {
            "text": "Este es un texto de prueba para generar un embedding.",
            "model_name": "text-embedding-3-small",
            "normalize": True
        }
    }
    action = DomainAction(**action_payload)
    
    # Enviar la acción a la cola del worker
    worker_queue = embedding_worker.queue_manager.get_queue_name("actions", "embedding")
    await redis_client.redis.lpush(worker_queue, action.model_dump_json())
    
    # Esperar la respuesta en la cola de callback
    _, response_data = await redis_client.redis.brpop(callback_queue, timeout=10)
    
    assert response_data is not None, "No se recibió respuesta del worker"
    
    response = DomainActionResponse.model_validate_json(response_data)
    
    assert response.success is True
    assert response.correlation_id == correlation_id
    assert "embedding" in response.data
    assert isinstance(response.data["embedding"], list)
    assert len(response.data["embedding"]) > 0
