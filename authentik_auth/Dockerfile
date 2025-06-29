# Use the official Authentik image (latest stable as of June 2025)
FROM ghcr.io/goauthentik/server:2025.6.0

# Copy startup script
COPY start.ps1 /start.ps1

# Switch to root to create directories with proper permissions
USER root

# Create necessary directories with proper permissions
RUN mkdir -p /etc/authentik/certs && \
    mkdir -p /etc/authentik/blueprints && \
    mkdir -p /etc/authentik/policies && \
    mkdir -p /media && \
    mkdir -p /certs && \
    mkdir -p /templates && \
    chown -R 1000:1000 /etc/authentik /media /certs /templates

# Copy local configuration files if needed
# COPY --chown=1000:1000 blueprints/ /etc/authentik/blueprints/
# COPY --chown=1000:1000 policies/ /etc/authentik/policies/

# Set default environment variables (can be overridden by docker-compose)
ENV AUTHENTIK_LOG_LEVEL=info
ENV AUTHENTIK_DEBUG=false
ENV AUTHENTIK_DISABLE_STARTUP_ANALYTICS=true
ENV AUTHENTIK_ERROR_REPORTING_ENABLED=false

# Switch back to non-root user
USER 1000

# Expose ports
EXPOSE 9000 9443 5558

# Set entrypoint to PowerShell
ENTRYPOINT ["pwsh", "-Command", "/start.ps1"]
