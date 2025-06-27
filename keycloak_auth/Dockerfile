# Usar la imagen oficial de Keycloak
FROM quay.io/keycloak/keycloak:25.0.1

# Variables de entorno para el usuario administrador
ENV KEYCLOAK_ADMIN=admin
ENV KEYCLOAK_ADMIN_PASSWORD=admin123

# Configuración de la base de datos PostgreSQL
ENV KC_DB=postgres
ENV KC_DB_URL=jdbc:postgresql://postgres_database:5432/keycloak
ENV KC_DB_USERNAME=keycloak
ENV KC_DB_PASSWORD=keycloak123

# Configuración del host y puerto
ENV KC_HOSTNAME=localhost
ENV KC_HTTP_PORT=8080

# Habilitar características de desarrollo (solo para desarrollo)
ENV KC_FEATURES=token-exchange,admin-fine-grained-authz,admin2

# Copiar la configuración del realm
COPY ./realm-export.json /opt/keycloak/data/import/realm-export.json

# Instalar el driver JDBC de PostgreSQL
RUN /opt/keycloak/bin/kc.sh build --db=postgres

# Exponer el puerto de Keycloak
EXPOSE 8080

# Comando para iniciar Keycloak en modo producción
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--import-realm"]
