# Propuesta de Módulo Común de Tiers: `common/tiers`

## 1. Introducción y Objetivos

Este documento describe la arquitectura y componentes de un nuevo módulo común, `common/tiers`, destinado a centralizar, estandarizar y gestionar toda la lógica de **límites, permisos y contabilidad de uso** relacionados con los tiers de los tenants en la plataforma Nooble4.

El objetivo principal es eliminar la lógica de tiers duplicada y dispersa en los diferentes microservicios, reemplazándola por un único punto de verdad (`Single Source of Truth`) que sea robusto, extensible y fácil de mantener.

**Principales responsabilidades del módulo:**

1.  **Definición Centralizada:** Proveer un esquema único y validado para la configuración de los límites de cada tier.
2.  **Validación Unificada:** Ofrecer herramientas (decoradores, funciones) para validar si una acción solicitada por un tenant cumple con los límites de su tier.
3.  **Contabilidad de Uso:** Proporcionar un mecanismo para registrar el consumo de recursos y validar contra cuotas (ej. tokens usados, documentos procesados).
4.  **Acceso Simplificado:** Facilitar a cualquier servicio el acceso a la configuración y al estado de uso actual de un tenant.

## 2. Estructura del Módulo `common/tiers`

El módulo se organizará de la siguiente manera dentro de la carpeta `common`:

```
common/
└── tiers/
    ├── __init__.py
    ├── models/
    │   ├── __init__.py
    │   ├── tier_config.py      # Modelos Pydantic para la configuración de tiers
    │   └── usage_models.py     # Modelos Pydantic para la contabilidad de uso
    ├── clients/
    │   ├── __init__.py
    │   └── tier_client.py      # Cliente para interactuar con el repositorio de tiers
    ├── services/
    │   ├── __init__.py
    │   ├── validation_service.py # Lógica de validación de límites y permisos
    │   └── usage_service.py      # Lógica para registrar y consultar el uso
    ├── decorators/
    │   ├── __init__.py
    │   └── validate_tier.py    # Decorador para aplicar validaciones en endpoints/handlers
    ├── repositories/
    │   ├── __init__.py
    │   └── tier_repository.py    # Abstracción para acceder a la BBDD de configuraciones/uso
    └── exceptions.py             # Excepciones personalizadas (e.g., TierLimitExceededError)
```

## 3. Componentes Detallados

### 3.1. Modelos (`common/tiers/models`)

#### `tier_config.py`

Definirá los modelos Pydantic que representan la estructura de configuración de un tier. Se basará en la unión de todos los límites identificados en el análisis previo.

```python
# common/tiers/models/tier_config.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class TierLimits(BaseModel):
    # Agent Management
    max_agents: int = Field(..., description="Número máximo de agentes que se pueden crear.")
    allow_custom_templates: bool = Field(False, description="Permite crear templates personalizados.")

    # Conversation
    max_conversation_history: int = Field(..., description="Máximo de mensajes a retener en el historial.")
    allow_conversation_persistence: bool = Field(True, description="Permite persistir las conversaciones.")

    # Query Service
    max_query_length: int = Field(..., description="Longitud máxima del query en caracteres.")
    allowed_query_models: List[str] = Field(..., description="Modelos de lenguaje permitidos para consultas.")

    # Embedding Service
    max_embedding_batch_size: int = Field(..., description="Tamaño máximo del lote para embeddings.")
    max_daily_embedding_tokens: int = Field(..., description="Cuota diaria de tokens para embedding.")

    # Ingestion Service
    max_file_size_mb: int = Field(..., description="Tamaño máximo de archivo para ingesta (MB).")
    max_daily_documents: int = Field(..., description="Número máximo de documentos a ingestar por día.")

    # General
    rate_limit_per_minute: int = Field(..., description="Límite de peticiones por minuto.")

class TierConfig(BaseModel):
    tier_name: str
    limits: TierLimits

# Ejemplo de configuración completa para todos los tiers
class AllTiersConfig(BaseModel):
    tiers: Dict[str, TierLimits]
```

#### `usage_models.py`

Modelos para registrar y consultar el uso de recursos.

```python
# common/tiers/models/usage_models.py
from pydantic import BaseModel, Field
from datetime import datetime

class UsageRecord(BaseModel):
    tenant_id: str
    resource: str # e.g., 'embedding_tokens', 'ingested_documents'
    amount: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TenantUsage(BaseModel):
    daily_embedding_tokens: int
    daily_documents: int
```

### 3.2. Repositorio (`common/tiers/repositories/tier_repository.py`)

Será la única capa que interactúe directamente con la base de datos (PostgreSQL) para obtener las configuraciones de los tiers y para leer/escribir los datos de uso de los tenants.

- **Fuente de Configuración:** La configuración de los tiers (`AllTiersConfig`) se cargará desde un archivo de configuración central (e.g., `settings.py` del AOS o un `config.yml`) o una tabla en la BBDD al iniciar el servicio que la necesite, y se cacheará en Redis para acceso rápido.
- **Fuente de Uso:** El estado de uso de cada tenant (`TenantUsage`) se almacenará en una tabla en PostgreSQL para persistencia y consistencia.

### 3.3. Cliente (`common/tiers/clients/tier_client.py`)

Abstracción de alto nivel que usarán los servicios para obtener información de tiers. Internamente, utilizará el `TierRepository`.

```python
# common/tiers/clients/tier_client.py
class TierClient:
    def __init__(self, repository: TierRepository):
        self._repository = repository

    async def get_tier_limits_for_tenant(self, tenant_id: str) -> Optional[TierLimits]:
        # Lógica para obtener el tier del tenant (desde AMS?)
        # y luego devolver la configuración de límites cacheados.
        pass

    async def get_tenant_usage(self, tenant_id: str) -> TenantUsage:
        # Devuelve el uso actual del tenant.
        pass
```

### 3.4. Servicios (`common/tiers/services`)

#### `validation_service.py`

Contendrá la lógica pura de validación. Recibirá el `tenant_id`, el recurso a validar y el valor, y devolverá `True` o lanzará una excepción `TierLimitExceededError`.

```python
# common/tiers/services/validation_service.py
class TierValidationService:
    def __init__(self, tier_client: TierClient):
        self._tier_client = tier_client

    async def validate_agent_creation(self, tenant_id: str):
        limits = await self._tier_client.get_tier_limits_for_tenant(tenant_id)
        # ... Lógica para comparar con el número actual de agentes ...
        if limit_exceeded:
            raise TierLimitExceededError("Número máximo de agentes alcanzado.")

    async def validate_query_length(self, tenant_id: str, length: int):
        # ...
        pass
```

#### `usage_service.py`

Encargado de la lógica de contabilidad: incrementar contadores, resetearlos (diariamente), etc.

```python
# common/tiers/services/usage_service.py
class TierUsageService:
    def __init__(self, repository: TierRepository):
        self._repository = repository

    async def increment_usage(self, tenant_id: str, resource: str, amount: float):
        # Lógica para actualizar el contador en la BBDD.
        await self._repository.increment_usage_counter(...)
```

### 3.5. Decorador (`common/tiers/decorators/validate_tier.py`)

La herramienta principal para que los servicios apliquen las validaciones de forma declarativa y limpia en sus `ActionHandlers` o endpoints de FastAPI.

```python
# common/tiers/decorators/validate_tier.py
from functools import wraps

def validate_tier(resource: str, amount_arg: str = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 1. Extraer tenant_id del contexto (e.g., del DomainAction)
            # 2. Obtener el servicio de validación (inyección de dependencias)
            # 3. Llamar al método de validación apropiado.
            #    Ej: validation_service.validate(tenant_id, resource, kwargs.get(amount_arg))
            # 4. Si la validación es exitosa, ejecutar func.
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Ejemplo de uso en un ActionHandler
# from common.tiers.decorators import validate_tier

class CreateAgentHandler(BaseActionHandler):
    @validate_tier(resource="agents.creation")
    async def handle(self, action: DomainAction) -> CreateAgentResponse:
        # ... la lógica del handler ...
```

## 4. Flujo de Operación

1.  **Configuración:** Un administrador define los límites para cada tier en un lugar centralizado (e.g., `config.yml`).
2.  **Inicio de Servicio:** Al arrancar, cada microservicio que necesite validación de tiers inicializa el `TierClient`, que carga y cachea en Redis la configuración de todos los tiers.
3.  **Llega una Petición:** Un `ActionHandler` (o endpoint) protegido por el decorador `@validate_tier` recibe una `DomainAction`.
4.  **Validación:**
    a. El decorador extrae el `tenant_id` y el recurso a validar.
    b. Invoca al `TierValidationService`.
    c. El servicio de validación usa el `TierClient` para obtener los límites del tier del tenant y su uso actual.
    d. Compara los valores. Si se excede un límite, lanza `TierLimitExceededError`, que es capturada por el worker/API para devolver una respuesta de error estandarizada.
5.  **Ejecución y Contabilidad:**
    a. Si la validación es exitosa, el handler se ejecuta.
    b. Al finalizar una operación que consume una cuota (e.g., procesar tokens), el servicio invoca al `TierUsageService` para registrar el consumo (`increment_usage`).

## 5. Plan de Implementación y Migración

1.  **Paso 1: Crear el Módulo `common/tiers`:** Implementar la estructura de archivos y los modelos Pydantic base (`tier_config.py`).
2.  **Paso 2: Implementar Repositorio y Cliente:** Desarrollar el `TierRepository` y el `TierClient`, enfocándose primero en leer la configuración desde un archivo y cachearla.
3.  **Paso 3: Implementar Servicios y Decorador:** Crear el `TierValidationService`, `TierUsageService` y el decorador `@validate_tier`.
4.  **Paso 4: Migración Servicio por Servicio:**
    a. Elegir un servicio piloto (e.g., `Query Service`).
    b. Integrar el `TierClient` y reemplazar la lógica de `settings.py` con llamadas al nuevo módulo.
    c. Aplicar el decorador `@validate_tier` a los handlers correspondientes.
    d. Eliminar la configuración de tiers local del servicio.
    e. Repetir para todos los demás servicios (`AES`, `CS`, `ES`, `IS`, `AMS`).

Este enfoque centralizado no solo reducirá drásticamente el código duplicado, sino que también mejorará la consistencia, facilitará la actualización de los límites y sentará las bases para un sistema de facturación y monitoreo más avanzado.

---

## 6. Estado de la Implementación

**La lógica descrita en este documento ha sido completamente implementada en el directorio `refactorizado/common/tiers`.**

Los puntos clave de la implementación son:

1.  **`TierResourceKey`**: Se ha creado una `Enum` para estandarizar todos los identificadores de recursos, eliminando el uso de strings mágicos.
2.  **Repositorio Simulado**: El `TierRepository` simula la interacción con una base de datos y un caché, cargando una configuración de tiers fija y gestionando contadores de uso en memoria, permitiendo pruebas unitarias y de integración sin dependencias externas.
3.  **Servicios Funcionales**: `TierValidationService` contiene un despachador que mapea cada `TierResourceKey` a un método de validación específico. `TierUsageService` se conecta directamente al repositorio para registrar el consumo.
4.  **Decorador Inteligente**: El decorador `@validate_tier` está implementado para extraer el `tenant_id` y los argumentos necesarios desde la llamada a la función, e invoca al servicio de validación de forma transparente.
5.  **Inyección de Dependencias (Simulada)**: Se ha incluido un mecanismo simple para inyectar el `TierValidationService` en el decorador, sentando las bases para una integración con frameworks como FastAPI.
