-- Script de inicialización para PostgreSQL
-- Este script crea las bases de datos y esquemas necesarios para todos los servicios

-- Crear usuarios para cada servicio
CREATE USER nooble_admin WITH PASSWORD 'nooble_admin_pass' SUPERUSER;
CREATE USER query_service WITH PASSWORD 'query_service_pass';
CREATE USER orchestrator_service WITH PASSWORD 'orchestrator_pass';
CREATE USER ingestion_service WITH PASSWORD 'ingestion_pass';
CREATE USER conversation_service WITH PASSWORD 'conversation_pass';
CREATE USER execution_service WITH PASSWORD 'execution_pass';
CREATE USER embedding_service WITH PASSWORD 'embedding_pass';
CREATE USER management_service WITH PASSWORD 'management_pass';
CREATE USER authentik_user WITH PASSWORD 'authentik_pass';

-- Crear base de datos principal
CREATE DATABASE nooble OWNER nooble_admin;

-- Conectar a la base de datos nooble
\c nooble;

-- Crear esquemas para cada servicio
CREATE SCHEMA IF NOT EXISTS query_schema AUTHORIZATION query_service;
CREATE SCHEMA IF NOT EXISTS orchestrator_schema AUTHORIZATION orchestrator_service;
CREATE SCHEMA IF NOT EXISTS ingestion_schema AUTHORIZATION ingestion_service;
CREATE SCHEMA IF NOT EXISTS conversation_schema AUTHORIZATION conversation_service;
CREATE SCHEMA IF NOT EXISTS execution_schema AUTHORIZATION execution_service;
CREATE SCHEMA IF NOT EXISTS embedding_schema AUTHORIZATION embedding_service;
CREATE SCHEMA IF NOT EXISTS management_schema AUTHORIZATION management_service;
CREATE SCHEMA IF NOT EXISTS shared_schema;

-- Otorgar permisos
GRANT ALL PRIVILEGES ON SCHEMA query_schema TO query_service;
GRANT ALL PRIVILEGES ON SCHEMA orchestrator_schema TO orchestrator_service;
GRANT ALL PRIVILEGES ON SCHEMA ingestion_schema TO ingestion_service;
GRANT ALL PRIVILEGES ON SCHEMA conversation_schema TO conversation_service;
GRANT ALL PRIVILEGES ON SCHEMA execution_schema TO execution_service;
GRANT ALL PRIVILEGES ON SCHEMA embedding_schema TO embedding_service;
GRANT ALL PRIVILEGES ON SCHEMA management_schema TO management_service;

-- Permisos para shared_schema
GRANT USAGE ON SCHEMA shared_schema TO query_service, orchestrator_service, ingestion_service, conversation_service, execution_service, embedding_service, management_service;
GRANT CREATE ON SCHEMA shared_schema TO nooble_admin;

-- Crear tablas compartidas en shared_schema
CREATE TABLE IF NOT EXISTS shared_schema.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shared_schema.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES shared_schema.tenants(id) ON DELETE CASCADE,
    external_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, external_id)
);

-- Tablas para Agent Management Service
CREATE TABLE IF NOT EXISTS management_schema.agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES shared_schema.tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    configuration JSONB DEFAULT '{}',
    capabilities JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

-- Tablas para Conversation Service
CREATE TABLE IF NOT EXISTS conversation_schema.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES shared_schema.tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES shared_schema.users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES management_schema.agents(id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_schema.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversation_schema.conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tablas para Ingestion Service
CREATE TABLE IF NOT EXISTS ingestion_schema.ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES shared_schema.tenants(id) ON DELETE CASCADE,
    job_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    source_info JSONB NOT NULL,
    progress JSONB DEFAULT '{}',
    error_info JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS ingestion_schema.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES shared_schema.tenants(id) ON DELETE CASCADE,
    job_id UUID REFERENCES ingestion_schema.ingestion_jobs(id) ON DELETE CASCADE,
    source_url TEXT,
    title VARCHAR(500),
    content_hash VARCHAR(64),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tablas para Query Service
CREATE TABLE IF NOT EXISTS query_schema.query_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES shared_schema.tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES shared_schema.users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES management_schema.agents(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    query_vector FLOAT[],
    results JSONB,
    metadata JSONB DEFAULT '{}',
    execution_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tablas para Execution Service
CREATE TABLE IF NOT EXISTS execution_schema.execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES shared_schema.tenants(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES management_schema.agents(id) ON DELETE CASCADE,
    execution_id VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) DEFAULT 'pending',
    input_data JSONB,
    output_data JSONB,
    error_info JSONB,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Índices para mejorar el rendimiento
CREATE INDEX idx_tenants_status ON shared_schema.tenants(status);
CREATE INDEX idx_users_tenant_id ON shared_schema.users(tenant_id);
CREATE INDEX idx_agents_tenant_id ON management_schema.agents(tenant_id);
CREATE INDEX idx_agents_status ON management_schema.agents(status);
CREATE INDEX idx_conversations_tenant_user ON conversation_schema.conversations(tenant_id, user_id);
CREATE INDEX idx_messages_conversation_id ON conversation_schema.messages(conversation_id);
CREATE INDEX idx_messages_created_at ON conversation_schema.messages(created_at);
CREATE INDEX idx_ingestion_jobs_tenant_status ON ingestion_schema.ingestion_jobs(tenant_id, status);
CREATE INDEX idx_documents_tenant_id ON ingestion_schema.documents(tenant_id);
CREATE INDEX idx_query_logs_tenant_user ON query_schema.query_logs(tenant_id, user_id);
CREATE INDEX idx_execution_logs_tenant_agent ON execution_schema.execution_logs(tenant_id, agent_id);

-- Crear funciones de utilidad
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Aplicar triggers para actualizar updated_at automáticamente
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON shared_schema.tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON shared_schema.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON management_schema.agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversation_schema.conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ingestion_jobs_updated_at BEFORE UPDATE ON ingestion_schema.ingestion_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON ingestion_schema.documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Otorgar permisos SELECT en tablas compartidas
GRANT SELECT ON shared_schema.tenants TO query_service, orchestrator_service, ingestion_service, conversation_service, execution_service, embedding_service, management_service;
GRANT SELECT ON shared_schema.users TO query_service, orchestrator_service, ingestion_service, conversation_service, execution_service, embedding_service, management_service;

-- Base de datos para Authentik
CREATE DATABASE authentik OWNER authentik_user;
GRANT ALL PRIVILEGES ON DATABASE authentik TO authentik_user;

-- Mensaje de confirmación
DO $$
BEGIN
    RAISE NOTICE 'Inicialización de base de datos completada exitosamente';
END
$$;