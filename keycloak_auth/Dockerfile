# Use the official Keycloak image with the latest stable version
FROM quay.io/keycloak/keycloak:26.0.0

# Set up environment variables for the admin user
ENV KEYCLOAK_ADMIN=admin
ENV KEYCLOAK_ADMIN_PASSWORD=admin123

# PostgreSQL database configuration
ENV KC_DB=postgres
ENV KC_DB_URL=jdbc:postgresql://postgres_database:5432/keycloak
ENV KC_DB_USERNAME=keycloak
ENV KC_DB_PASSWORD=keycloak123
ENV KC_DB_SCHEMA=public

# Host and port configuration
ENV KC_HOSTNAME=localhost
ENV KC_HTTP_PORT=8080
ENV KC_HTTP_RELATIVE_PATH=/auth

# Enable features (development only)
# Using only features that are valid for Keycloak 26.0.0
ENV KC_FEATURES=token-exchange,admin-fine-grained-authz,admin-api,account-api

# Health check options
ENV KC_HEALTH_ENABLED=true
ENV KC_METRICS_ENABLED=true

# Copy the realm configuration
COPY ./realm-export.json /opt/keycloak/data/import/realm-export.json

# Install PostgreSQL JDBC driver and build the server
RUN /opt/keycloak/bin/kc.sh build --db=postgres

# Expose the Keycloak port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080/health/ready || exit 1

# Start Keycloak in production mode
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--import-realm"]
