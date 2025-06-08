# Gestión del Ciclo de Vida de Colas Redis

## Introducción

Este documento analiza cómo se gestionan actualmente las colas Redis en el sistema nooble4, identificando problemas potenciales de acumulación de recursos y proponiendo soluciones para optimizar su ciclo de vida.

## Estado Actual de las Colas Redis

### 1. Estructura de Colas

El sistema nooble4 utiliza un patrón de colas en Redis para la comunicación asíncrona entre servicios:

```
{domain}:{action_type}:{tier}:{task_id}
```

Ejemplos:
- `execution:agent_run:professional:12345`
- `embedding:generate:enterprise:67890`
- `query:search:advance:24680`
- `execution:callback:free:13579`

### 2. Análisis del Código Actual

El `DomainQueueManager` en `common/services/domain_queue_manager.py` gestiona la creación y consumo de colas:

```python
async def enqueue_action(self, domain: str, action: DomainAction, tier: str = None) -> str:
    """
    Encola una acción en la cola específica para su domain y tier.
    """
    # Determinar tier desde acción si no se proporciona
    tier = tier or action.tenant_tier
    
    # Obtener nombre de cola
    queue_name = self._get_queue_name(domain, tier, action.task_id)
    
    # Serializar y guardar
    serialized_action = action.json()
    await self.redis.rpush(queue_name, serialized_action)
    
    # Incrementar contador
    await self._increment_metrics(domain, tier)
    
    return queue_name

async def dequeue_action(self, domain: str, tier: str, task_id: str = None) -> Optional[Dict[str, Any]]:
    """
    Desencola una acción de la cola específica.
    """
    queue_name = self._get_queue_name(domain, tier, task_id)
    
    # Desencolar (LPOP para FIFO)
    serialized_action = await self.redis.lpop(queue_name)
    
    if not serialized_action:
        return None
    
    # Deserializar
    return json.loads(serialized_action)
```

### 3. Problema Identificado: Ciclo de Vida Incompleto

**El sistema actual presenta deficiencias en la gestión del ciclo de vida completo de las colas:**

1. **No hay limpieza automática**: Las claves de Redis asociadas a tareas completadas no se eliminan sistemáticamente
2. **Potencial acumulación**: Las colas permanecen en Redis incluso después de completar el procesamiento
3. **Ausencia de tracking**: No hay mecanismo para rastrear todas las colas creadas para una tarea específica
4. **Sin control de tiempo de vida**: No se establece un TTL automático para las colas

## Impacto del Problema

Esta gestión incompleta del ciclo de vida puede llevar a:

1. **Consumo excesivo de memoria**: Acumulación continua de colas sin usar en Redis
2. **Problemas de rendimiento**: Redis debe manejar un número creciente de claves
3. **Dificultad de depuración**: Difícil diferenciar entre colas activas e inactivas
4. **Posibles fugas de recursos**: Las colas nunca liberadas consumen recursos del sistema

## Solución Propuesta

### 1. Registro de Colas por Tarea

Implementar un sistema de tracking que registre todas las colas creadas para una tarea específica:

```python
async def enqueue_action(self, domain: str, action: DomainAction, tier: str = None) -> str:
    # Código existente...
    
    # NUEVO: Registrar cola en set de tareas
    task_queues_key = f"task_queues:{action.task_id}"
    await self.redis.sadd(task_queues_key, queue_name)
    
    # Establecer TTL de seguridad (1 hora)
    await self.redis.expire(task_queues_key, 3600)
    
    return queue_name
```

### 2. Limpieza Explícita de Colas

Implementar un método para limpiar todas las colas asociadas a una tarea cuando finaliza:

```python
async def clean_task_queues(self, task_id: str) -> int:
    """
    Limpia todas las colas asociadas a un task_id específico.
    
    Args:
        task_id: ID de la tarea
        
    Returns:
        Número de colas eliminadas
    """
    # Obtener clave que contiene todas las colas de esta tarea
    task_queues_key = f"task_queues:{task_id}"
    
    # Obtener todas las colas registradas para esta tarea
    queue_names = await self.redis.smembers(task_queues_key)
    
    if not queue_names:
        return 0
    
    # Eliminar cada cola
    deleted_count = 0
    for queue_name in queue_names:
        # Eliminar cola
        deleted = await self.redis.delete(queue_name)
        deleted_count += deleted
    
    # Eliminar registro de colas
    await self.redis.delete(task_queues_key)
    
    return deleted_count
```

### 3. Integración con Callbacks

Integrar la limpieza en el procesamiento de callbacks, especialmente en el `ExecutionCallbackAction` que señaliza que una tarea está completa:

```python
# En agent_orchestrator_service/handlers/domain_action_handlers.py
async def process_execution_callback(self, action: ExecutionCallbackAction):
    """
    Procesa callback de ejecución y limpia recursos.
    """
    try:
        # Procesamiento normal del callback
        await self._send_result_to_websocket(
            session_id=action.session_id,
            result=action.result,
            status=action.status
        )
        
        # NUEVO: Limpiar colas asociadas a esta tarea
        deleted_count = await self.queue_manager.clean_task_queues(action.task_id)
        
        logger.info(
            f"Callback procesado y recursos liberados: {action.task_id}, "
            f"{deleted_count} colas eliminadas"
        )
        
    except Exception as e:
        logger.error(f"Error procesando callback: {str(e)}")
        
    return {"success": True}
```

### 4. Limpieza Programada de Colas Huérfanas

Implementar un proceso periódico que limpie colas antiguas que podrían haberse quedado huérfanas:

```python
# En un worker periódico
async def clean_orphaned_queues(self):
    """
    Limpia colas huérfanas (sin actividad reciente).
    """
    # Buscar todas las colas de las últimas 24 horas
    all_task_queues = await self.redis.keys("task_queues:*")
    
    for task_queue_key in all_task_queues:
        # Verificar si la tarea tiene TTL
        ttl = await self.redis.ttl(task_queue_key)
        
        # Si es -1 (no tiene TTL) o es más de 24 horas, limpiar
        if ttl == -1 or ttl > 86400:
            task_id = task_queue_key.split(":")[-1]
            
            # Limpiar colas de esta tarea
            await self.queue_manager.clean_task_queues(task_id)
            logger.info(f"Limpieza automática de colas para tarea: {task_id}")
```

## Beneficios de la Implementación

1. **Optimización de recursos**: Liberación sistemática de memoria Redis
2. **Mejor observabilidad**: Registro claro de las colas creadas por tarea
3. **Prevención de fugas**: Se evita la acumulación indefinida de colas
4. **Mejor depuración**: Facilita la identificación de colas activas vs. inactivas

## Consideraciones para la Implementación

1. **Consistencia**: Asegurar que la limpieza no elimine colas que aún están en uso
2. **Transacciones**: Considerar el uso de transacciones Redis para operaciones de limpieza
3. **Métricas**: Implementar métricas para monitorear la creación y limpieza de colas
4. **Gradualidad**: Implementar primero en entorno de desarrollo y observar comportamiento

## Próximos Pasos

1. Extender `DomainQueueManager` con el método `clean_task_queues`
2. Modificar los handlers de callbacks para incluir la limpieza
3. Implementar métricas para monitorear el ciclo de vida de las colas
4. Crear un worker periódico para limpieza de colas huérfanas
5. Validar la implementación con pruebas de carga
