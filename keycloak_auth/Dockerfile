# Use the official Keycloak image from Quay.io
FROM quay.io/keycloak/keycloak:25.0.1

# Set environment variables for the admin user
# WARNING: Use environment variables or secrets in a real production environment
ENV KEYCLOAK_ADMIN=admin
ENV KEYCLOAK_ADMIN_PASSWORD=admin

# Copy the realm configuration file into the container
COPY ./realm-export.json /opt/keycloak/data/import/realm-export.json

# Expose the default Keycloak port
EXPOSE 8080

# Command to start Keycloak and import the realm on startup
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start-dev", "--import-realm"]
