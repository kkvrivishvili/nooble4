-- Crear usuario kong con contraseña y privilegios necesarios
CREATE USER kong WITH PASSWORD 'kong123' SUPERUSER CREATEDB CREATEROLE LOGIN;

-- Crear base de datos para Kong
CREATE DATABASE kong OWNER kong ENCODING 'UTF8' LC_COLLATE='C' LC_CTYPE='C' TEMPLATE template0;

-- Crear base de datos para Konga
CREATE DATABASE konga OWNER kong ENCODING 'UTF8' LC_COLLATE='C' LC_CTYPE='C' TEMPLATE template0;

-- Conceder todos los privilegios al usuario kong en sus bases de datos
GRANT ALL PRIVILEGES ON DATABASE kong TO kong;
GRANT ALL PRIVILEGES ON DATABASE konga TO kong;

-- Conceder privilegios adicionales necesarios para Kong
\c kong

-- Habilitar extensiones necesarias para Kong
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS http;
CREATE EXTENSION IF NOT EXISTS hstore;

-- Asegurar que el usuario tenga los privilegios necesarios
ALTER DATABASE kong SET standard_conforming_strings = on;
ALTER DATABASE kong SET escape_string_warning = off;

-- Configurar parámetros adicionales para Kong
ALTER SYSTEM SET max_connections = '1000';
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET wal_buffers = '7864kB';
ALTER SYSTEM SET checkpoint_completion_target = '0.9';
ALTER SYSTEM SET default_statistics_target = '100';
ALTER SYSTEM SET random_page_cost = '1.1';
ALTER SYSTEM SET effective_io_concurrency = '200';
ALTER SYSTEM SET effective_cache_size = '768MB';

-- Recargar la configuración
SELECT pg_reload_conf();
