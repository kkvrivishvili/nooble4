#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER kong;
    CREATE DATABASE kong;
    GRANT ALL PRIVILEGES ON DATABASE kong TO kong;
EOSQL
