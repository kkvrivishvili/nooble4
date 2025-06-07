"""
Punto de entrada principal para el servicio de embeddings.

Este script inicia el worker para procesar Domain Actions de embeddings,
configurando el entorno y manejando la ejecución.
"""

import logging
import asyncio
import signal
import sys
from typing import Set

from common.redis_pool import get_redis_client
from common.services.action_processor import ActionProcessor
from embedding_service.workers.embedding_worker import EmbeddingWorker
from embedding_service.config.settings import get_settings

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """
    Servicio principal de embeddings.
    
    Maneja el ciclo de vida del worker y las interrupciones.
    """
    
    def __init__(self):
        """Inicializa el servicio."""
        self.shutdown_event = asyncio.Event()
        self.worker = None
        
    async def start(self):
        """Inicia el servicio."""
        try:
            # Inicializar Redis y ActionProcessor
            redis_client = get_redis_client(settings.redis_url)
            action_processor = ActionProcessor(redis_client)
            
            # Crear e iniciar worker
            self.worker = EmbeddingWorker(redis_client, action_processor)
            logger.info("Iniciando EmbeddingWorker...")
            
            # Manejar señales de terminación
            self._setup_signal_handlers()
            
            # Iniciar worker
            await self.worker.start()
            
            # Esperar señal de apagado
            await self.shutdown_event.wait()
            
            # Detener worker
            await self.worker.stop()
            logger.info("Worker detenido correctamente.")
            
        except Exception as e:
            logger.error(f"Error iniciando servicio: {str(e)}")
            sys.exit(1)
    
    def _setup_signal_handlers(self):
        """Configura handlers para señales del sistema."""
        loop = asyncio.get_event_loop()
        signals = (signal.SIGINT, signal.SIGTERM) if sys.platform != 'win32' else (signal.SIGINT,)
        
        for sig in signals:
            loop.add_signal_handler(
                sig, lambda s=sig: asyncio.create_task(self._shutdown(s))
            )
    
    async def _shutdown(self, sig):
        """
        Maneja el apagado ordenado del servicio.
        
        Args:
            sig: Señal recibida
        """
        logger.info(f"Recibida señal {sig.name}. Iniciando apagado...")
        self.shutdown_event.set()


async def main():
    """Función principal."""
    logger.info(f"Iniciando servicio de Embeddings, versión: 1.0")
    
    # Mostrar configuración
    logger.info(f"Configuración cargada - Modelo predeterminado: {settings.default_embedding_model}")
    logger.info(f"Límites: max_batch_size={settings.max_batch_size}, max_text_length={settings.max_text_length}")
    
    # Iniciar servicio
    service = EmbeddingService()
    await service.start()


if __name__ == "__main__":
    # Ejecutar bucle principal
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Apagado por usuario.")
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        sys.exit(1)
