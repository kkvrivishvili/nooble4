# Use the official Kong image with the latest stable version
FROM kong:3.7.1

# Set environment variables for Kong
ENV KONG_DATABASE=postgres
ENV KONG_PG_HOST=postgres_database
ENV KONG_PG_DATABASE=kong
ENV KONG_PG_USER=kong
ENV KONG_PG_PASSWORD=kong123

# Copy the custom configuration file
COPY kong.conf /etc/kong/kong.conf

# Install any required Kong plugins
# Example: RUN luarocks install kong-plugin-your-plugin

# Expose Kong ports
EXPOSE 8000 8001 8002 8003 8004 8443 8444 8445 8446

# Health check
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
  CMD kong health || exit 1

# Set the default command
CMD ["kong", "docker-start", "--conf", "/etc/kong/kong.conf"]
