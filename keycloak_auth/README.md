# Keycloak Authentication Setup for Nooble4

This directory contains the necessary files to run Keycloak for authentication and authorization in the Nooble4 project.

## Quick Start

To start the Keycloak server, run the following command from this directory:

```bash
docker-compose up -d --build
```

This will build the Docker image and start the Keycloak container in detached mode.

## Accessing the Admin Console

- **URL**: [http://localhost:8080](http://localhost:8080)
- **Admin Username**: `admin`
- **Admin Password**: `admin`

## Realm Configuration

The server is pre-configured with a realm defined in `realm-export.json`:

- **Realm Name**: `nooble4-realm`

### Client Application

- **Client ID**: `nooble4-backend-client`
- **Client Secret**: `your-client-secret` ( **IMPORTANT**: Change this in a production environment!)

### Test User

- **Username**: `testuser`
- **Password**: `test`

## Stopping the Service

To stop the Keycloak container, run:

```bash
docker-compose down
```