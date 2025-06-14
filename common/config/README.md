# Módulo de Configuración Común (`refactorizado.common.config`)

Este módulo centraliza la gestión de la configuración para todos los microservicios del proyecto Nooble4. Su objetivo es proporcionar una forma estandarizada, consistente y segura de definir y acceder a las configuraciones.

## Principios Clave

- **Centralización:** Las definiciones de configuración base y específicas del servicio residen aquí.
- **Herencia:** Las configuraciones específicas del servicio heredan de una clase base común (`CommonAppSettings`).
- **Tipado Estricto:** Uso de `Pydantic` para la validación y el tipado de datos de configuración.
- **Carga desde el Entorno:** Las configuraciones se cargan principalmente desde variables de entorno y archivos `.env`, facilitando la gestión en diferentes entornos (desarrollo, staging, producción).
- **Seguridad:** Los secretos y datos sensibles se gestionan a través de variables de entorno y no se hardcodean.

## Estructura del Módulo

```
refactorizado/common/config/
├── __init__.py                 # Exporta las configuraciones principales.
├── base_settings.py            # Define CommonAppSettings, la clase base para todas las configuraciones.
└── service_settings/           # Subdirectorio para las clases de configuración específicas de cada servicio.
    ├── __init__.py             # Exporta todas las clases de configuración específicas.
    ├── agent_orchestrator.py   # Define OrchestratorSettings.
    ├── agent_execution.py      # Define ExecutionSettings.
    ├── ... (un archivo .py por cada servicio)
```

### `base_settings.py`

- Contiene la clase `CommonAppSettings(BaseSettings)` de `pydantic-settings`.
- Define todos los parámetros de configuración que son comunes a la mayoría o todos los servicios, como:
  - `service_name`, `service_version`, `environment`, `log_level`
  - Configuraciones de Redis (`redis_host`, `redis_port`, etc.)
  - Configuraciones CORS
  - Parámetros de telemetría, timeouts HTTP, etc.
- Utiliza `SettingsConfigDict` para configurar la carga desde archivos `.env` y el manejo de campos extra.

### `service_settings/`

- Cada archivo dentro de este subdirectorio (ej. `agent_orchestrator.py`) define una clase de configuración específica para un microservicio (ej. `OrchestratorSettings`).
- Estas clases heredan de **`CommonAppSettings`**: Define las configuraciones comunes a todos los servicios (ej. `ENVIRONMENT`, `LOG_LEVEL`, `REDIS_URL`) que son utilizadas por `BaseWorker`, `BaseService` y otros componentes de `common`.
- Definen sus propios parámetros específicos del servicio.
- Especifican un `env_prefix` único en su `model_config` (ej. `AOS_`) para que las variables de entorno se carguen correctamente para ese servicio.

### `__init__.py` (en `refactorizado/common/config/`)

- Exporta `CommonAppSettings`.
- Re-exporta todas las clases de configuración específicas del servicio desde el submódulo `service_settings`.
- Esto permite a los servicios importar sus configuraciones de manera sencilla:
  ```python
  from refactorizado.common.config import OrchestratorSettings, EmbeddingServiceSettings
  ```

## Uso en los Microservicios

Cada microservicio, en su propio directorio `config/` (ej. `agent_orchestrator_service/config/`), tendrá:

1.  **`settings.py`:**
    ```python
    from functools import lru_cache
    # Importa la clase de settings específica del servicio desde la ubicación común centralizada
    from refactorizado.common.config import OrchestratorSettings # O cualquier otra clase de settings

    @lru_cache()
    def get_settings() -> OrchestratorSettings:
        """Retorna la instancia de configuración para este servicio."""
        return OrchestratorSettings()
    ```

2.  **`__init__.py`:**
    ```python
    from .settings import get_settings
    # Opcionalmente, re-exportar la clase de Settings si se necesita acceso directo a ella además de get_settings()
    # from refactorizado.common.config import OrchestratorSettings

    __all__ = ['get_settings'] # , 'OrchestratorSettings']
    ```

Los servicios luego usan `get_settings()` para acceder a su configuración:

```python
from mi_servicio.config import get_settings

settings = get_settings()
print(settings.service_name)
print(settings.redis_host)
print(settings.mi_parametro_especifico)
```

## Archivo `.env`

Se recomienda un archivo `.env` centralizado en el directorio `refactorizado/` (con una plantilla en `refactorizado/.env.example`). Las clases `Settings` están configuradas para cargar desde este archivo por defecto.
Las variables de entorno deben seguir el prefijo definido en cada clase de configuración específica del servicio (ej. `AOS_SERVICE_NAME`, `ES_OPENAI_API_KEY`).
