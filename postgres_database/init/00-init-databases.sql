-- Script de inicialización de todas las bases de datos necesarias
-- Este script se ejecuta automáticamente al iniciar el contenedor de Postgres

-- Conectar como superusuario
\c postgres

-- ==================== KONG ====================
-- Crear usuario y base de datos para Kong
CREATE USER kong WITH PASSWORD 'kong123' CREATEDB LOGIN;
CREATE DATABASE kong OWNER kong;

-- ==================== KONGA ====================
-- Crear usuario y base de datos para Konga
CREATE USER konga WITH PASSWORD 'konga123' CREATEDB LOGIN;
CREATE DATABASE konga OWNER konga;

-- ==================== KEYCLOAK ====================
-- Crear usuario y base de datos para Keycloak
CREATE USER keycloak WITH PASSWORD 'keycloak123' CREATEDB LOGIN;
CREATE DATABASE keycloak OWNER keycloak;

-- ==================== PERMISOS ====================
GRANT ALL PRIVILEGES ON DATABASE kong TO kong;
GRANT ALL PRIVILEGES ON DATABASE konga TO konga;
GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;

-- Cambiar a la base de datos kong para crear extensiones
\c kong
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Volver a postgres
\c postgres