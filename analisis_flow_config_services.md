# Análisis del Flujo de Configuraciones entre Servicios

## 1. Situación Actual

Después de analizar el código de los tres servicios principales (`agent_execution_service`, `query_service` y `embedding_service`), se observa que:

1. **Estructura de Configuración:**
   - Cada servicio tiene su propio archivo de configuración (`settings.py`) que extiende clases base definidas en `common/config/`
   - Las configuraciones son estáticas y se cargan al inicio del servicio
   - No existe un mecanismo explícito para pasar configuraciones dinámicas de modelos entre servicios

2. **Comunicación entre Servicios:**
   - Se utiliza `DomainAction` para enviar comandos entre servicios
   - Los payloads incluyen datos específicos de la acción, pero no configuraciones globales
   - Las configuraciones de modelos (ej. `model=payload.model.value`) están embebidas en cada solicitud individual

3. **Principales Debilidades:**
   - Configuraciones hardcodeadas en cada servicio
   - Duplicación de configuraciones entre servicios
   - Dificultad para cambiar dinámicamente parámetros de modelos

## 2. Propuesta de Diseño: Centralización y Propagación de Configuraciones

### 2.1 Principio General

El `agent_execution_service`, como punto de entrada del sistema, debería centralizar todas las configuraciones de modelos (Groq, OpenAI) y propagarlas a los servicios subordinados cuando sea necesario, siguiendo un enfoque de cascada:

```
Agent Execution Service → Query Service → Embedding Service
```

### 2.2 Flujo de Configuración Propuesto

#### A. Configuración Centralizada en Agent Execution Service

```python
# agent_execution_service/config/model_settings.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from enum import Enum

class ModelProvider(str, Enum):
    OPENAI = "openai"
    GROQ = "groq"
    MISTRAL = "mistral"
    # Otros proveedores futuros

class ModelConfiguration(BaseModel):
    """Configuración dinámica para modelos de LLM y embeddings."""
    
    # Configuración para modelos de chat
    chat_model: str = Field(..., description="Nombre del modelo de chat a utilizar")
    chat_provider: ModelProvider = Field(..., description="Proveedor del modelo de chat")
    chat_api_key: str = Field(..., description="API key para el proveedor de chat")
    temperature: float = Field(0.7, description="Temperature para generación")
    max_tokens: int = Field(1000, description="Máximo de tokens a generar")
    
    # Configuración para embeddings
    embedding_model: str = Field(..., description="Nombre del modelo de embedding")
    embedding_provider: ModelProvider = Field(..., description="Proveedor del modelo de embedding")
    embedding_api_key: str = Field(..., description="API key para el proveedor de embeddings")
    embedding_dimensions: int = Field(1536, description="Dimensiones del embedding")
    
    # Configuraciones adicionales
    timeout_seconds: int = Field(60, description="Timeout para operaciones de modelos")
    retry_attempts: int = Field(3, description="Intentos de retry para operaciones fallidas")
    
    # Configuraciones específicas de proveedores
    provider_configs: Dict[str, Any] = Field(default_factory=dict, description="Configuraciones específicas por proveedor")
```

#### B. Propagación de Configuraciones en Solicitudes

Modificar los métodos de los clientes para incluir la configuración dinámica en cada solicitud:

```python
# agent_execution_service/clients/query_client.py (modificado)
async def query_simple(
    self,
    payload: Dict[str, Any],
    tenant_id: str,
    session_id: str,
    task_id: uuid.UUID,
    model_config: Optional[ModelConfiguration] = None,  # Nueva configuración dinámica
    timeout: Optional[int] = None
) -> Dict[str, Any]:
    """
    Realiza una consulta simple con RAG integrado.
    Incluye configuración dinámica de modelos si se proporciona.
    """
    # Agregar configuración de modelo si está disponible
    if model_config:
        payload["model_configuration"] = model_config.model_dump()
        
    # Resto del método igual
    # ...
```

#### C. Recepción y Uso en Query Service

```python
# query_service/services/query_service.py (modificado)
async def _handle_simple(self, action: DomainAction) -> Dict[str, Any]:
    """Maneja la acción query.simple."""
    # Validar y parsear payload
    payload = ChatRequest.model_validate(action.data)
    
    # Extraer configuración dinámica si existe
    model_config = None
    if "model_configuration" in action.data:
        from common.models.model_config import ModelConfiguration
        model_config = ModelConfiguration.model_validate(action.data["model_configuration"])
    
    # Usar configuración dinámica o fallback a configuración estática
    chat_model = payload.model.value
    chat_api_key = self.app_settings.groq_api_key
    temperature = payload.temperature
    max_tokens = payload.max_tokens
    
    if model_config:
        chat_model = model_config.chat_model
        chat_api_key = model_config.chat_api_key
        temperature = model_config.temperature
        max_tokens = model_config.max_tokens
    
    # Resto del método usando las configuraciones establecidas
    # ...
```

#### D. Propagación a Embedding Service

```python
# query_service/clients/embedding_client.py (modificado)
async def request_query_embedding(
    self,
    query_text: str,
    tenant_id: str,
    session_id: str,
    task_id: UUID,
    trace_id: Optional[UUID] = None,
    model: Optional[str] = None,
    model_config: Optional[Dict[str, Any]] = None  # Nueva configuración dinámica
) -> DomainActionResponse:
    """
    Solicita embedding para query.
    Incluye configuración dinámica si está disponible.
    """
    # Preparar payload base
    payload = {
        "input": query_text,
        "model": model or self.default_model
    }
    
    # Agregar configuración dinámica si está disponible
    if model_config:
        payload["model_configuration"] = model_config
    
    # Resto del método igual
    # ...
```

## 3. Implementación por Fases

### Fase 1: Refactorización del Modelo de Configuraciones
- Crear la clase `ModelConfiguration` en `common/models/model_config.py`
- Actualizar `ExecutionServiceSettings` para incluir instancia de configuración por defecto
- Implementar métodos para cargar configuraciones desde variables de entorno o archivos JSON

### Fase 2: Modificación de Clientes
- Actualizar `QueryClient` para incluir configuraciones en payloads
- Actualizar `EmbeddingClient` para propagar configuraciones 
- Añadir soporte para timeout dinámico basado en configuraciones

### Fase 3: Actualización de Handlers
- Modificar handlers para extraer y aplicar configuraciones dinámicas
- Implementar lógica de fallback a configuraciones estáticas cuando no se proporcionen dinámicas
- Agregar validación de compatibilidad entre configuraciones y acciones

### Fase 4: Testing y Validación
- Pruebas unitarias para cada componente con distintas configuraciones
- Pruebas de integración para validar flujo completo
- Validación de rendimiento y latencia con distintas configuraciones

## 4. Beneficios del Nuevo Diseño

1. **Flexibilidad**: Cambio dinámico de proveedores y modelos sin reiniciar servicios
2. **Coherencia**: Una única fuente de verdad para configuraciones de modelos
3. **Seguridad**: Control centralizado de API keys y acceso a servicios externos
4. **Extensibilidad**: Fácil adición de nuevos proveedores o modelos
5. **Observabilidad**: Trazabilidad de qué configuraciones se usaron en cada solicitud

## 5. Consideraciones de Rendimiento

- El tamaño de payloads aumentará ligeramente por las configuraciones adicionales
- La serialización/deserialización añade overhead mínimo
- El sistema de caché para API clients puede optimizarse para reutilizar conexiones con mismas configuraciones

## 6. Ejemplo de Flujo Completo

1. **Cliente → Agent Execution Service**:
   ```json
   {
     "message": "¿Cuál es la capital de Francia?",
     "model_preferences": {
       "provider": "groq",
       "model": "llama2-70b-4096"
     }
   }
   ```

2. **Agent Execution Service** construye `ModelConfiguration` basada en preferencias y envía a Query Service

3. **Query Service** utiliza configuración para llamar a Groq y también la propaga a Embedding Service para RAG

4. **Embedding Service** utiliza la configuración propagada para generar embeddings consistentes

5. La respuesta final mantiene metadatos de qué configuraciones se utilizaron, permitiendo trazabilidad completa

## 7. Conclusión

Este enfoque de propagación de configuraciones dinámicas desde Agent Execution Service asegura un sistema flexible que puede adaptarse a cambios en proveedores y modelos sin modificar código o reiniciar servicios, manteniendo la consistencia en toda la cadena de procesamiento.
