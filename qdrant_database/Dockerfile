# Usar la imagen oficial de Qdrant
# Puedes especificar una versión si es necesario, por ejemplo: qdrant/qdrant:v1.9.0
# Para ver las versiones disponibles: https://hub.docker.com/r/qdrant/qdrant/tags
FROM qdrant/qdrant

# Exponer el puerto gRPC y el puerto HTTP
# El puerto 6333 es para HTTP y el 6334 para gRPC
EXPOSE 6333
EXPOSE 6334

# Copiar el archivo de configuración personalizado al contenedor
# Qdrant buscará este archivo en /qdrant/config/config.yaml
COPY ./config/config.yaml /qdrant/config/config.yaml

# Opcionalmente, se puede especificar un punto de entrada si se necesitan comandos adicionales al iniciar.
# Por defecto, la imagen base ya tiene un punto de entrada configurado para iniciar Qdrant.
