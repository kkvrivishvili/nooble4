-- Script de inicialización para PostgreSQL
-- Versión mínima para Authentik

-- Crear usuario administrador para PostgreSQL
DO $$
BEGIN
    -- Crear usuario admin solo si no existe
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nooble_admin') THEN
        CREATE USER nooble_admin WITH PASSWORD 'nooble_admin_pass' SUPERUSER;
        RAISE NOTICE 'Usuario nooble_admin creado correctamente';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Error al crear el usuario nooble_admin: %', SQLERRM;
END
$$;

-- Crear base de datos para Authentik si no existe
SELECT 'CREATE DATABASE authentik WITH OWNER nooble_admin ENCODING ''UTF8'' LC_COLLATE = ''en_US.utf8'' LC_CTYPE = ''en_US.utf8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'authentik')\gexec

-- Crear usuario para Authentik
DO $$
BEGIN
    -- Crear usuario para Authentik si no existe
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authentik_user') THEN
        CREATE USER authentik_user WITH PASSWORD 'authentik_pass';
        RAISE NOTICE 'Usuario authentik_user creado correctamente';
    END IF;
    
    -- Otorgar permisos básicos al usuario de Authentik
    GRANT CONNECT ON DATABASE authentik TO authentik_user;
    
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Error al configurar el usuario authentik_user: %', SQLERRM;
END
$$;

-- Conectar a la base de datos authentik para configurar permisos adicionales
\c authentik;

-- Asegurarse de que el esquema público tenga los permisos correctos
GRANT ALL ON SCHEMA public TO nooble_admin;
GRANT CREATE, USAGE ON SCHEMA public TO authentik_user WITH GRANT OPTION;

-- Configurar permisos predeterminados para futuras tablas
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authentik_user;

-- Otorgar todos los permisos necesarios en la base de datos
GRANT ALL PRIVILEGES ON DATABASE authentik TO authentik_user;
ALTER DATABASE authentik OWNER TO authentik_user;

-- Grant all privileges on the public schema
GRANT ALL ON SCHEMA public TO authentik_user WITH GRANT OPTION;

-- Grant all privileges on all objects in the public schema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO authentik_user WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO authentik_user WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO authentik_user WITH GRANT OPTION;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO authentik_user WITH GRANT OPTION;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO authentik_user WITH GRANT OPTION;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO authentik_user WITH GRANT OPTION;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TYPES TO authentik_user WITH GRANT OPTION;

-- Mensaje de finalización exitosa
DO $$
BEGIN
    RAISE NOTICE 'Configuración de base de datos para Authentik completada exitosamente';
    RAISE NOTICE 'Base de datos: authentik';
    RAISE NOTICE 'Usuario: authentik_user';
    RAISE NOTICE 'Host: postgres_database';
    RAISE NOTICE 'Puerto: 5432';
END
$$;