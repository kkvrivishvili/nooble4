# Propuesta de Estandarización de Configuración para Nooble4

## 1. Introducción

Este documento describe la propuesta para estandarizar la gestión de configuraciones a través de todos los microservicios del proyecto Nooble4. El objetivo es mejorar la claridad, consistencia, seguridad y facilidad de mantenimiento del sistema de configuración.

La estandarización se basa en el uso de `Pydantic` y `pydantic-settings` para la validación y carga de configuraciones desde variables de entorno y archivos `.env`.

## 2. Principios Generales

- **Fuente Única de Verdad**: Para cada servicio, su archivo `config/settings.py` será la fuente única de verdad para todas las configuraciones y sus valores por defecto.
- **Carga desde el Entorno**: Las configuraciones deben ser cargables desde variables de entorno, permitiendo diferentes configuraciones por entorno (desarrollo, staging, producción) sin modificar el código.
- **Manejo Seguro de Secretos**: Las API keys, contraseñas y otros datos sensibles nunca deben estar hardcodeados en el código ni tener valores por defecto en el código. Deben cargarse exclusivamente desde el entorno.
- **Consistencia Estructural**: Todos los servicios seguirán la misma estructura de directorios y archivos para la configuración.
- **Claridad**: Separación clara entre configuraciones (variables) y constantes (valores fijos).

## 3. Estructura de Directorios y Archivos

Cada microservicio (`<nombre_servicio>_service`) deberá tener la siguiente estructura en su carpeta de configuración:

```
<nombre_servicio>_service/
|-- config/
|   |-- __init__.py
|   |-- settings.py
|   |-- constants.py  (Opcional)
|-- ... (otros módulos del servicio)
```

### 3.1. `config/settings.py`

- Este archivo **importará** la clase de configuración específica del servicio (ej. `ServiceSpecificSettings`) desde la ubicación centralizada en `refactorizado/common/config/service_settings/`.
- Proveerá una función `get_settings()` cacheada que instancia y retorna la clase de configuración importada.
- Ya **no definirá** la clase de configuración del servicio directamente.

**Ejemplo (`<nombre_servicio>_service/config/settings.py`):**
```python
from functools import lru_cache

# Importa la clase de settings específica del servicio desde la ubicación común centralizada
from refactorizado.common.config.service_settings import ServiceSpecificSettings 
# (Asumiendo que ServiceSpecificSettings se define en refactorizado/common/config/service_settings/__init__.py o un módulo específico)

@lru_cache()
def get_settings() -> ServiceSpecificSettings:
    """Retorna la instancia de configuración para este servicio."""
    return ServiceSpecificSettings()

# La clase ServiceSpecificSettings (que hereda de CommonAppSettings)
# y su model_config (con el prefijo de entorno específico del servicio)
# se definen ahora en refactorizado/common/config/service_settings/<nombre_servicio_settings>.py
```

### 3.2. `config/constants.py` (Opcional)

- Este archivo es opcional y solo debe usarse para constantes verdaderamente inmutables y específicas del servicio.
- **Ejemplos**: Enums para tipos de acción interna, nombres de colas internas fijas (si no se derivan del `service_name` o `domain_name`), nombres de endpoints fijos que no cambian entre entornos.
- **NO debe contener**: Valores que podrían cambiar (TTLs, URLs de otros servicios, límites, flags de features, etc.). Estos son configuraciones y pertenecen a `settings.py`.

**Ejemplo (`<nombre_servicio>_service/config/constants.py`):**
```python
from enum import Enum

SERVICE_VERSION = "1.0.2-beta"

class InternalActionTypes(Enum):
    PROCESS_DATA = "process_data"
    VALIDATE_INPUT = "validate_input"

class FixedEndpointPaths:
    STATUS_INTERNAL = "/_internal/status"
```

### 3.3. `config/__init__.py`

- Exportará la clase de configuración principal (importada en `settings.py` desde la ubicación común) y la función `get_settings` para fácil acceso desde otras partes del servicio.

**Ejemplo (`<nombre_servicio>_service/config/__init__.py`):**
```python
from .settings import get_settings

# ServiceSpecificSettings es ahora importada indirectamente a través de get_settings,
# o podría re-exportarse explícitamente si se importa también en .settings.py
# from refactorizado.common.config.service_settings import ServiceSpecificSettings
# __all__ = ['ServiceSpecificSettings', 'get_settings']

# Alternativamente, si solo se necesita get_settings:
__all__ = ['get_settings']
```

## 4. Configuración Común Centralizada (`refactorizado/common/config/`)

La configuración común y las configuraciones específicas de cada servicio se gestionarán de forma centralizada en el directorio `refactorizado/common/config/`.

La estructura propuesta es:
```
refactorizado/
|-- common/
|   |-- config/
|   |   |-- __init__.py
|   |   |-- settings.py  # Define CommonAppSettings
|   |   |-- service_settings/ # Subdirectorio para configuraciones específicas de servicio
|   |   |   |-- __init__.py
|   |   |   |-- agent_orchestrator.py # Define OrchestratorSettings
|   |   |   |-- agent_execution.py    # Define ExecutionSettings
|   |   |   |-- ... (un archivo por servicio)
|-- ...
```

### 4.1. `refactorizado/common/config/settings.py` (Configuración Base Común)

- Define la clase base `CommonAppSettings` que todas las configuraciones específicas de servicio heredarán.
- Esta clase utiliza `pydantic_settings.BaseSettings`.

**Contenido (`refactorizado/common/config/settings.py`):**
```python
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class CommonAppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra='ignore', env_file='.env')

    service_name: str = Field(..., description="Nombre del servicio, ej: 'agent-orchestrator-service'. Requerido.")
    environment: str = Field("development", description="Entorno de ejecución (development, staging, production).")
    log_level: str = Field("INFO", description="Nivel de logging (DEBUG, INFO, WARNING, ERROR).")

    redis_url: str = Field("redis://localhost:6379/0", description="URL de conexión a Redis.")
    redis_host: str = Field("localhost", description="Host de Redis.")
    redis_port: int = Field(6379, description="Puerto de Redis.")
    redis_db: int = Field(0, description="Base de datos Redis.")
    redis_password: Optional[str] = Field(None, description="Contraseña de Redis (opcional).")

    database_url: Optional[str] = Field(None, description="URL de conexión a la base de datos principal (opcional).")
    # ... otros campos comunes ...
```

### 4.2. `refactorizado/common/config/service_settings/<nombre_servicio>.py` (Configuraciones Específicas)

- Cada servicio tendrá su propio archivo Python dentro de `refactorizado/common/config/service_settings/`.
- Este archivo definirá la clase de configuración específica del servicio (ej. `OrchestratorSettings`), que hereda de `CommonAppSettings`.
- Aquí se especifica el `env_prefix` particular del servicio y sus campos de configuración únicos.

**Ejemplo (`refactorizado/common/config/service_settings/mi_servicio_settings.py`):**
```python
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ..settings import CommonAppSettings # Importa la base común

class MiServicioSettings(CommonAppSettings):
    # Modelo de configuración con el prefijo específico del servicio
    model_config = SettingsConfigDict(env_prefix='MISERVICIO_', env_file='.env', extra='ignore')

    # Configuraciones específicas del servicio
    specific_parameter: str = Field("default_value", description="Un parámetro específico del servicio.")
    another_specific_parameter: int = Field(123, description="Otro parámetro.")
    service_api_key: str = Field(..., description="API Key para un servicio externo, requerido.")

    # Hereda campos de CommonAppSettings como service_name, environment, etc.
    # El service_name debe ser provisto por una variable de entorno (ej. MISERVICIO_SERVICE_NAME)
    # o se puede definir un valor por defecto aquí si es apropiado para este servicio en particular.
    # service_name: str = Field("mi-servicio-especifico", description="Nombre del servicio.")
```

### 4.3. `refactorizado/common/config/__init__.py` y `service_settings/__init__.py`

- `refactorizado/common/config/service_settings/__init__.py` puede exportar todas las clases de configuración específicas para facilitar su importación.
  ```python
  # refactorizado/common/config/service_settings/__init__.py
  from .agent_orchestrator import OrchestratorSettings
  from .agent_execution import ExecutionSettings
  # ... y así para cada servicio

  __all__ = ['OrchestratorSettings', 'ExecutionSettings', ...]
  ```
- `refactorizado/common/config/__init__.py` exportará `CommonAppSettings` y podría re-exportar las configuraciones de `service_settings`.
  ```python
  # refactorizado/common/config/__init__.py
  from .settings import CommonAppSettings
  from . import service_settings # Para acceder como service_settings.OrchestratorSettings
  # o directamente: from .service_settings import OrchestratorSettings, ...

  __all__ = ['CommonAppSettings', 'service_settings'] # o lista explícita de clases
  ```

Esta estructura centralizada asegura que todas las definiciones de configuración Pydantic estén en un solo lugar, mejorando la coherencia y la mantenibilidad.

## 5. Manejo de Secretos

- **Nunca hardcodear secretos**: API keys, contraseñas, tokens, etc., no deben tener valores por defecto en el código.
- **Carga desde el entorno**: Utilizar `Field(...)` (sin valor por defecto) para campos requeridos que son secretos. Pydantic forzará su carga desde una variable de entorno.
  ```python
  class ServiceSettings(CommonAppSettings):
      model_config = SettingsConfigDict(env_prefix='MYSVC_', env_file='.env')
      my_api_key: str = Field(..., description="API Key requerida para X.")
      # Pydantic buscará MYSVC_MY_API_KEY en el entorno.
  ```

## 6. Variables de Entorno y Archivos `.env`

- **Prefijos**: Cada servicio usará un prefijo único para sus variables de entorno (ej. `AOS_`, `AES_`, `CONVERSATION_`) definido en `SettingsConfigDict(env_prefix=...)`.
- **Archivos `.env`**: Para desarrollo local, se recomienda el uso de archivos `.env` en la raíz de cada servicio o en la raíz del proyecto. Pydantic (`BaseSettings`) los carga automáticamente si se especifica `env_file='.env'` en `SettingsConfigDict`.

## 7. Acciones Específicas de Refactorización (Resumen del Análisis)

- **Todos los Servicios**: Revisar `constants.py` y mover cualquier valor configurable a `settings.py`.
- **`common/config.py`**: Implementar `CommonAppSettings` como se describe arriba. Eliminar o refactorizar `get_service_settings`.
- **Conversation Service**: Crear `config/__init__.py`. Asegurar que `supabase_url`, `supabase_key` se carguen desde el entorno.
- **Embedding Service**: Crear `config/__init__.py`. Eliminar el hardcoding de `openai_api_key` en `get_settings()` y asegurar que se cargue desde el entorno. Mover el diccionario `OPENAI_MODELS` a `constants.py` si es estático, o gestionarlo como configuración si sus valores (ej. `max_tokens`) pueden variar.
- **Ingestion Service**: Modificar `get_settings()` para seguir el patrón estándar de instanciar `IngestionServiceSettings()` directamente, confiando en la herencia de `CommonAppSettings` y Pydantic para la carga. Eliminar la redundancia masiva entre `constants.py` y los defaults en `settings.py`.
- **Query Service**: Asegurar que la llamada en `get_settings()` sea `QueryServiceSettings(**base_settings.model_dump())` o simplemente `QueryServiceSettings()` si `base_settings` ya es un diccionario compatible o si `CommonAppSettings` se maneja correctamente por herencia directa.
- **Todos los `get_settings()`**: Estandarizar a la forma simple `@lru_cache() def get_settings(): return ServiceSpecificSettings()`.

## 8. Conclusión

La adopción de esta propuesta de estandarización resultará en un sistema de configuración más robusto, seguro, y fácil de gestionar para el proyecto Nooble4. Facilitará la configuración en diferentes entornos y reducirá la probabilidad de errores debidos a configuraciones inconsistentes o hardcodeadas.
