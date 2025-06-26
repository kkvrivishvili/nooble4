# Kong API Gateway Setup for Nooble4

This directory is a placeholder for any future Kong-specific configuration files. The main setup is managed within the root `docker-compose.yml`.

## Overview

We use Kong as an API Gateway to manage, secure, and orchestrate our microservices. It acts as a single entry point for all client requests.

For easy administration, we use **Konga**, an open-source GUI for Kong.

## Required Configuration

Before starting the services, you must add the following variable to your main `.env` file. This password is used by Kong to connect to its dedicated PostgreSQL database.

```
KONG_PG_PASSWORD=your-secure-password
```

## Accessing Services

- **Konga UI**: [http://localhost:1337](http://localhost:1337)
  - On your first visit, Konga will ask you to create an admin user.
  - After creating the user, you will need to configure the connection to Kong. Use `http://kong:8001` as the Kong Admin URL.

- **Kong Proxy (HTTP)**: `http://localhost:8081`
  - All your API traffic will be routed through this port.

- **Kong Admin API**: `http://localhost:8011`
  - This is the API that Konga and other tools use to configure Kong.

## How It Works

The `docker-compose.yml` file orchestrates three services for our Kong setup:

1.  **`postgres`**: The main database service has been configured to run an initialization script (`postgres_database/init/init-kong-db.sh`) that creates a dedicated `kong` database and `kong` user.
2.  **`kong-migrations`**: A one-time job that runs `kong migrations bootstrap` to set up the necessary tables in the `kong` database.
3.  **`kong`**: The main API Gateway container.
4.  **`konga`**: The web-based GUI to manage Kong.
