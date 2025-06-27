# Use a specific version of Konga that's known to work well with PostgreSQL
FROM pantsel/konga:0.14.9

# Set environment variables for PostgreSQL connection
ENV NODE_ENV=production

# Database configuration
ENV DB_ADAPTER=postgres
ENV DB_HOST=postgres_database
ENV DB_PORT=5432
ENV DB_USER=konga
ENV DB_PASSWORD=konga123
ENV DB_DATABASE=konga

# Konga configuration
ENV TOKEN_SECRET=some-secret-token
ENV KONGA_HOOK_TIMEOUT=120000
ENV KONGA_LOG_LEVEL=debug
ENV NODE_TLS_REJECT_UNAUTHORIZED=0

# Install specific version of pg driver for PostgreSQL 15 compatibility
USER root
RUN npm uninstall pg -g || true
RUN npm install -g pg@8.11.3

# Clean up npm cache to reduce image size
RUN npm cache clean --force

# Switch back to non-root user
USER node

# Create necessary directories
RUN mkdir -p /app/tmp

# Expose Konga port
EXPOSE 1337

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:1337/health || exit 1

# Set the default command with production flag
CMD ["node", "./app/start.js", "--prod"]
