#!/bin/bash

# Generate REDIS_PASSWORD if not set
if [ -z "$REDIS_PASSWORD" ]; then
    export REDIS_PASSWORD=$(openssl rand -base64 36 | tr -d '=')
fi

# Generate AUTHENTIK_SECRET_KEY if not set
if [ -z "$AUTHENTIK_SECRET_KEY" ]; then
    export AUTHENTIK_SECRET_KEY=$(openssl rand -base64 60 | tr -d '=')
fi

# Run server or worker based on argument
case "$1" in
    server)
        /authentik/entrypoint.sh server
        ;;
    worker)
        /authentik/entrypoint.sh worker
        ;;
    *)
        echo "Unknown command: $1"
        exit 1
        ;;
esac
