# Requerimientos y Responsabilidades del Conversation Service (Parte 3)

## Implementación Técnica

### Almacenamiento y Base de Datos

El Conversation Service requiere una estrategia de almacenamiento optimizada para:

1. **Escritura Intensiva**: Capacidad para almacenar grandes volúmenes de mensajes.
2. **Lectura Eficiente**: Recuperación rápida del historial por diferentes criterios.
3. **Búsqueda**: Capacidad de búsqueda por contenido y metadatos.
4. **Escalabilidad**: Diseño que permita escalar horizontalmente.

Recomendaciones de implementación:

```python
# Ejemplo de implementación con MongoDB
class ConversationRepository:
    def __init__(self, mongodb_client):
        self.db = mongodb_client.get_database("conversations_db")
        self.conversations = self.db.conversations
        self.messages = self.db.messages
        self.states = self.db.conversation_states
        
        # Índices para optimizar consultas
        self._ensure_indexes()
        
    def _ensure_indexes(self):
        # Índices para conversaciones
        self.conversations.create_index([("tenant_id", 1), ("created_at", -1)])
        self.conversations.create_index([("tenant_id", 1), ("status", 1)])
        self.conversations.create_index([("tenant_id", 1), ("tags", 1)])
        self.conversations.create_index([("tenant_id", 1), ("participants.participant_id", 1)])
        
        # Índices para mensajes
        self.messages.create_index([("conversation_id", 1), ("timestamp", 1)])
        self.messages.create_index([("tenant_id", 1), ("conversation_id", 1), ("timestamp", 1)])
        self.messages.create_index([("tenant_id", 1), ("sender_id", 1)])
        
        # Índices para estados
        self.states.create_index([("conversation_id", 1), ("state_key", 1)])
        self.states.create_index([("tenant_id", 1), ("conversation_id", 1)])
```

### Consideraciones de Caching

Para mejorar el rendimiento, se recomienda implementar una estrategia de caché:

```python
class ConversationCache:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl_config = {
            "conversation": 3600,  # 1 hora
            "messages": 1800,      # 30 minutos
            "state": 900           # 15 minutos
        }
    
    async def get_conversation(self, tenant_id, conversation_id):
        key = f"conversation:{tenant_id}:{conversation_id}"
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    async def cache_conversation(self, tenant_id, conversation_id, data):
        key = f"conversation:{tenant_id}:{conversation_id}"
        await self.redis.set(key, json.dumps(data), ex=self.ttl_config["conversation"])
    
    async def get_recent_messages(self, tenant_id, conversation_id):
        key = f"messages:{tenant_id}:{conversation_id}"
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    async def cache_recent_messages(self, tenant_id, conversation_id, messages):
        key = f"messages:{tenant_id}:{conversation_id}"
        await self.redis.set(key, json.dumps(messages), ex=self.ttl_config["messages"])
```

## Requisitos de Seguridad y Compliance

### Protección de Datos

El servicio debe implementar medidas de seguridad para:

1. **Encriptación**: Datos sensibles deben estar encriptados en reposo y en tránsito.
2. **Control de Acceso**: Estricta validación de permisos basados en tenant y roles.
3. **Sanitización**: Validación y sanitización de entradas para prevenir inyecciones.
4. **Auditoría**: Logging de accesos y modificaciones para fines de auditoría.

Ejemplo de implementación de control de acceso:

```python
class ConversationPermissionHandler:
    def __init__(self, auth_service_client):
        self.auth_client = auth_service_client
        
    async def validate_conversation_access(self, tenant_id, user_id, conversation_id, permission_level="read"):
        """Valida si el usuario tiene acceso a la conversación."""
        try:
            # Verificar si el usuario pertenece al tenant
            tenant_validation = await self.auth_client.validate_user_tenant(user_id, tenant_id)
            if not tenant_validation.get("valid", False):
                return False
            
            # Verificar permiso específico para la conversación
            permission = await self.auth_client.check_permission(
                user_id=user_id,
                resource_type="conversation",
                resource_id=conversation_id,
                permission=permission_level
            )
            
            return permission.get("has_permission", False)
            
        except Exception as e:
            logger.error(f"Error validando permisos: {str(e)}")
            return False
```

### Retención de Datos y Compliance

El servicio debe soportar políticas de retención de datos:

1. **TTL Configurable**: Permitir configurar tiempo de vida por tenant y tipo de dato.
2. **Archivado Automático**: Mover conversaciones antiguas a almacenamiento más económico.
3. **Borrado Selectivo**: Permitir borrar datos específicos (derecho al olvido).
4. **Exportación GDPR**: Facilitar la exportación de datos para cumplir con solicitudes GDPR.

Ejemplo de implementación:

```python
class DataRetentionManager:
    def __init__(self, db_client, retention_config):
        self.db = db_client
        self.config = retention_config
        
    async def apply_retention_policies(self, tenant_id):
        """Aplica políticas de retención para un tenant."""
        now = datetime.utcnow()
        
        # Obtener configuración para el tenant
        tenant_config = await self.get_tenant_config(tenant_id)
        retention_days = tenant_config.get("conversation_retention_days", 365)
        
        # Calcular fecha límite
        cutoff_date = now - timedelta(days=retention_days)
        
        # Archivar conversaciones antiguas
        await self.archive_old_conversations(tenant_id, cutoff_date)
        
        # Eliminar datos muy antiguos si está configurado
        if tenant_config.get("hard_delete_enabled", False):
            hard_delete_days = tenant_config.get("hard_delete_days", 730)  # 2 años
            hard_delete_date = now - timedelta(days=hard_delete_days)
            await self.permanently_delete_data(tenant_id, hard_delete_date)
    
    async def permanently_delete_data(self, tenant_id, cutoff_date):
        """Elimina permanentemente datos antiguos."""
        # Implementar con extremo cuidado y auditoría
```
