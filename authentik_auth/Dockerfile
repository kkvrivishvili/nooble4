# authentik_auth/Dockerfile
FROM ghcr.io/goauthentik/server:2025.6.0

# Set environment variables
ENV AUTHENTIK_LISTEN__HTTP=0.0.0.0:9000 \
    AUTHENTIK_PORT_HTTP=9000 \
    AUTHENTIK_PORT_HTTPS=9443 \
    AUTHENTIK_EMAIL__USE_TLS="false" \
    AUTHENTIK_EMAIL__USE_SSL="false" \
    AUTHENTIK_EMAIL__TIMEOUT=10 \
    AUTHENTIK_EMAIL__VERIFY_CERTS=true \
    AUTHENTIK_ERROR_REPORTING__ENABLED="false" \
    AUTHENTIK_DISABLE_STARTUP_ANALYTICS=true

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:9000/-/health/live/ || exit 1

# Default command (can be overridden in docker-compose)
CMD ["server"]
