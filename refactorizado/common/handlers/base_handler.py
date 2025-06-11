import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseHandler(ABC):
    """
    Clase base abstracta para todos los handlers del sistema.

    Proporciona funcionalidades comunes como:
    - Un logger configurado con el nombre de la clase hija.
    - Un patrón para inicialización asíncrona explícita (carga diferida).
    - Un contrato de ejecución (`execute`) que los workers utilizarán.
    """
    def __init__(self, service_name: str, **kwargs):
        """
        Inicialización básica síncrona del handler.
        Establece el estado inicial para la carga diferida.
        """
        if not service_name:
            raise ValueError("El parámetro 'service_name' no puede ser nulo o vacío.")
        self.service_name = service_name
        self._logger = logging.getLogger(f"{self.service_name}.{self.__class__.__name__}")
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """
        Realiza la inicialización asíncrona del handler de forma segura.

        Este método es idempotente y seguro para concurrencia. El worker
        (o quien cree el handler) puede llamarlo para asegurarse de que el
        handler está listo antes de usarse. La lógica de inicialización
        real solo se ejecutará una vez.
        """
        if self._initialized:
            return
        
        async with self._init_lock:
            # Doble comprobación por si otra corrutina lo inicializó
            # mientras se esperaba por el lock.
            if self._initialized:
                return
            
            await self._async_init()
            self._initialized = True

    async def _async_init(self) -> None:
        """
        Método a ser sobreescrito por las subclases que necesiten
        realizar operaciones asíncronas en su inicialización.

        Por defecto, no hace nada.
        """
        pass

    @abstractmethod
    async def execute(self) -> Dict[str, Any]:
        """
        Punto de entrada principal para la ejecución de la lógica del handler.

        Este método será llamado por el BaseWorker después de que el handler
        haya sido instanciado e inicializado.

        Debe ser implementado por las subclases para realizar la acción principal
        y devolver un diccionario que represente el payload de la respuesta (si aplica).
        Si no hay datos de respuesta, puede devolver un diccionario vacío.
        """
        raise NotImplementedError("Las subclases deben implementar 'execute'.")
