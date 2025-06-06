# Agent Execution Service

Servicio para la ejecución de agentes utilizando LangChain. Este servicio se encarga de procesar solicitudes de ejecución de agentes, interactuar con los servicios externos necesarios, y devolver los resultados.

## Arquitectura

El servicio está construido con las siguientes tecnologías:
- **FastAPI**: Framework web para APIs
- **Redis**: Para gestión de colas y comunicación asíncrona
- **LangChain**: Para ejecución de agentes de IA
- **Pydantic**: Para validación de datos y modelos
- **Httpx**: Cliente HTTP asíncrono

## Flujo de Ejecución

1. El servicio recibe solicitudes de ejecución a través de una cola Redis
2. El worker procesa las solicitudes y las convierte en acciones de dominio
3. El handler de ejecución:
   - Obtiene la configuración del agente desde Agent Management Service
   - Obtiene el historial de conversación desde Conversation Service
   - Ejecuta el agente utilizando LangChain
   - Guarda los mensajes en Conversation Service
   - Envía el resultado a través de una cola de callback

## Configuración

El servicio utiliza variables de entorno con el prefijo `EXECUTION_`:

```
# Configuración básica
EXECUTION_SERVICE_NAME=agent-execution-service
EXECUTION_SERVICE_VERSION=0.1.0
EXECUTION_LOG_LEVEL=INFO

# Redis
EXECUTION_REDIS_URL=redis://localhost:6379/0

# URLs de servicios externos
EXECUTION_EMBEDDING_SERVICE_URL=http://localhost:8001
EXECUTION_QUERY_SERVICE_URL=http://localhost:8002
EXECUTION_CONVERSATION_SERVICE_URL=http://localhost:8004
EXECUTION_AGENT_MANAGEMENT_SERVICE_URL=http://localhost:8003

# Configuración de ejecución
EXECUTION_DEFAULT_AGENT_TYPE=conversational
EXECUTION_MAX_ITERATIONS=5
EXECUTION_MAX_EXECUTION_TIME=120

# Worker
EXECUTION_WORKER_SLEEP_SECONDS=1.0
```

## Endpoints

El servicio no expone endpoints REST para ejecución de agentes, ya que toda la comunicación se realiza a través de colas Redis. Sin embargo, proporciona endpoints de salud:

- `GET /health`: Verifica el estado del servicio
- `GET /ready`: Verifica si el servicio está listo para recibir solicitudes

## Testing

Para ejecutar las pruebas:

```bash
pytest
```

## Desarrollo

Para ejecutar el servicio en modo desarrollo:

```bash
uvicorn main:app --reload --port 8005
```
