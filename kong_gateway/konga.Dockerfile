# Use a specific version of Konga image that's known to work with PostgreSQL 15
FROM pantsel/konga:0.14.9

# Install a more recent version of the pg driver
USER root
RUN npm install pg@latest
USER node
