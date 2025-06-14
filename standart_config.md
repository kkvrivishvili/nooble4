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

- Este archivo es opcional y solo debe usarse para constantes verdaderamente inmutables y específicas del servicio que no son adecuadas para las clases de configuración Pydantic.
- **Ejemplos**: Enums para tipos de acción interna, estados de tareas, tipos de documentos, o rutas de endpoints fijas del propio servicio.
- **NO debe contener**: Valores que podrían cambiar entre entornos (TTLs, URLs de otros servicios, límites, flags de features), la versión del servicio (manejada en `CommonAppSettings`), nombres de colas Redis configurables, o cualquier lógica de tiers.
- Durante la refactorización, muchos elementos que antes estaban en `constants.py` (como `VERSION`, definiciones de nombres de colas, o límites por tier) se han movido a las clases `Settings` correspondientes o se ha determinado que se construirán dinámicamente a partir de la configuración.

**Ejemplo (`<nombre_servicio>_service/config/constants.py` después de la limpieza):**
```python
from enum import Enum

class TaskStates(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentTypes(str, Enum):
    PDF = "pdf"
    TEXT = "text"

class FixedEndpointPaths:
    HEALTH_CHECK = "/health"
    MAIN_RESOURCE = "/resource"
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
|   |   |-- base_settings.py  # Define CommonAppSettings
|   |   |-- service_settings/ # Subdirectorio para configuraciones específicas de servicio
|   |   |   |-- __init__.py
|   |   |   |-- agent_orchestrator.py # Define OrchestratorSettings
|   |   |   |-- agent_execution.py    # Define ExecutionSettings
|   |   |   |-- ... (un archivo por servicio)
|-- ...
```

### 4.1. `refactorizado/common/config/base_settings.py` (Configuración Base Común)

- Define la clase base `CommonAppSettings` que todas las configuraciones específicas de servicio heredarán.
- Esta clase utiliza `pydantic_settings.BaseSettings`.

**Contenido (`refactorizado/common/config/base_settings.py`):**
```python
from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl

class CommonAppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra='ignore', env_file='.env')

    # Identificación y Entorno del Servicio
    service_name: str = Field(..., description="Nombre del servicio, ej: 'agent-orchestrator'. Requerido.")
    service_version: str = Field("0.1.0", description="Versión del servicio.")
    environment: str = Field("development", description="Entorno de ejecución (development, staging, production).")
    log_level: str = Field("INFO", description="Nivel de logging (DEBUG, INFO, WARNING, ERROR).")
    enable_telemetry: bool = Field(False, description="Habilitar telemetría y seguimiento distribuido.")

    # Configuración HTTP Común
    http_timeout_seconds: int = Field(30, description="Timeout global para clientes HTTP salientes.")
    max_retries: int = Field(3, description="Número máximo de reintentos para operaciones críticas.")
    worker_sleep_seconds: float = Field(0.1, description="Tiempo de espera para los workers entre ciclos de polling.")

    # Configuración CORS
    cors_origins: List[Union[AnyHttpUrl, str]] = Field(default_factory=lambda: ["*"], description="Orígenes permitidos para CORS.")
    cors_allow_credentials: bool = Field(True, description="Permitir credenciales en CORS.")
    cors_allow_methods: List[str] = Field(default_factory=lambda: ["*"], description="Métodos HTTP permitidos por CORS.")
    cors_allow_headers: List[str] = Field(default_factory=lambda: ["*"], description="Cabeceras HTTP permitidas por CORS.")

    # Configuración de API Key (para proteger los propios endpoints del servicio)
    api_key_header_name: str = Field("X-API-Key", description="Nombre de la cabecera para la API key de acceso al servicio.")

    # Configuración de Redis
    redis_url: Optional[str] = Field(None, description="URL de conexión a Redis completa (ej. redis://user:pass@host:port/db?ssl_cert_reqs=required). Si se provee, otras variables redis_* pueden ser ignoradas.")
    redis_host: str = Field("localhost", description="Host de Redis.")
    redis_port: int = Field(6379, description="Puerto de Redis.")
    redis_password: Optional[str] = Field(None, description="Contraseña de Redis.")
    redis_db: int = Field(0, description="Número de la base de datos Redis.")
    redis_use_ssl: bool = Field(False, description="Usar SSL para la conexión a Redis.")
    redis_socket_connect_timeout: int = Field(5, description="Timeout en segundos para la conexión del socket Redis.")
    redis_max_connections: Optional[int] = Field(None, description="Número máximo de conexiones en el pool de Redis.")
    redis_health_check_interval: int = Field(30, description="Intervalo en segundos para el health check de la conexión Redis.")
    redis_decode_responses: bool = Field(True, description="Decodificar automáticamente las respuestas de Redis a UTF-8.")

    # Configuración de Base de Datos (Opcional por servicio)
    database_url: Optional[str] = Field(None, description="URL de conexión a la base de datos principal (ej. PostgreSQL, MySQL).")

    # Otros campos comunes pueden añadirse aquí según evolucionen las necesidades.
```

### 4.2. `refactorizado/common/config/service_settings/<nombre_servicio>.py` (Configuraciones Específicas)

- Cada servicio tendrá su propio archivo Python dentro de `refactorizado/common/config/service_settings/`.
- Este archivo definirá la clase de configuración específica del servicio (ej. `OrchestratorSettings`), que hereda de `CommonAppSettings`.
- Aquí se especifica el `env_prefix` particular del servicio y sus campos de configuración únicos.

**Ejemplo (`refactorizado/common/config/service_settings/mi_servicio_settings.py`):**
```python
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ..base_settings import CommonAppSettings # Importa la base común

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
  from .base_settings import CommonAppSettings
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

- **Prefijos**: Cada servicio usará un prefijo único para sus variables de entorno (ej. `AGENT_ORCHESTRATOR_`, `AGENT_EXECUTION_`, `CONVERSATION_`) definido en `SettingsConfigDict(env_prefix=...)` en su clase de settings específica.
- **Archivos `.env`**: Para desarrollo local, se recomienda el uso de archivos `.env`. Pydantic (`BaseSettings`) los carga automáticamente (por defecto busca un archivo `.env` en el directorio actual). Se provee una plantilla general en `refactorizado/.env.example` que debe ser copiada a `refactorizado/.env` y personalizada. Los servicios pueden cargar este `.env` común si `env_file='.env'` está en su `SettingsConfigDict` y se ejecutan desde el directorio `refactorizado`, o pueden tener sus propios archivos `.env` locales si es necesario (aunque se prefiere el centralizado).

## 7. Resumen de la Refactorización Realizada

La estandarización de la configuración implicó los siguientes cambios clave a través del codebase:

- **Centralización de Clases de Configuración**:
  - Se creó una clase base `CommonAppSettings` en `refactorizado/common/config/base_settings.py`, que contiene todas las configuraciones compartidas entre servicios (nombre del servicio, versión, entorno, logging, CORS, parámetros de Redis, etc.).
  - Las clases de configuración específicas de cada servicio (ej. `OrchestratorSettings`, `EmbeddingSettings`) se movieron a `refactorizado/common/config/service_settings/`, heredando de `CommonAppSettings` y definiendo sus propios parámetros y prefijos de entorno.

- **Simplificación de `config/settings.py` en Servicios Individuales**:
  - Los archivos `settings.py` dentro de cada servicio ahora simplemente importan su clase de configuración específica desde la ubicación centralizada y la instancian a través de una función `get_settings()` cacheada.

- **Limpieza de Archivos `constants.py`**:
  - Se revisaron los archivos `constants.py` en cada servicio.
  - Se eliminaron valores configurables, como la `VERSION` del servicio (ahora en `CommonAppSettings`), nombres de colas Redis (ahora derivados de la configuración en las clases `Settings`), y cualquier parámetro relacionado con tiers.
  - `constants.py` ahora solo contiene verdaderas constantes inmutables específicas del dominio del servicio (ej. Enums para estados, tipos de documentos, rutas de API fijas del propio servicio).

- **Eliminación de Lógica de Tiers de las Configuraciones de Servicio**:
  - Todas las configuraciones relacionadas con límites o comportamientos específicos por tier de usuario (ej. `max_requests_per_hour_by_tier`, `feature_enabled_by_tier`) fueron eliminadas de las clases `Settings` de los servicios individuales.
  - Esta lógica será manejada por un futuro módulo de gestión de tiers centralizado (`refactorizado/common/tiers`).

- **Manejo de Nombres de Colas Redis**:
  - Los nombres de las colas Redis ya no se definen como constantes fijas. En su lugar, se construyen dinámicamente utilizando parámetros de las clases `Settings` (como `domain_name`, `service_name`, y sufijos/segmentos específicos de cola definidos en la configuración del servicio).

- **Archivo `.env.example`**:
  - Se creó un archivo `refactorizado/.env.example` para servir como plantilla de las variables de entorno comunes y específicas de los servicios, facilitando la configuración del entorno de desarrollo.

- **Actualización de `CommonAppSettings`**:
  - Se añadieron nuevos campos relevantes a `CommonAppSettings`, incluyendo `service_version`, `worker_sleep_seconds`, `enable_telemetry`, y parámetros detallados para la conexión Redis (timeouts, SSL, max_connections, etc.).

- **Consistencia en `__init__.py`**:
  - Se estandarizaron los archivos `__init__.py` en las carpetas `config/` de los servicios y en `refactorizado/common/config/` para exportar adecuadamente las configuraciones y funciones `get_settings`.

## 8. Conclusión

La adopción de esta propuesta de estandarización resultará en un sistema de configuración más robusto, seguro, y fácil de gestionar para el proyecto Nooble4. Facilitará la configuración en diferentes entornos y reducirá la probabilidad de errores debidos a configuraciones inconsistentes o hardcodeadas.
