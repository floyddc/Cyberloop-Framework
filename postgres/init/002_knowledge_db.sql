SELECT 'CREATE DATABASE knowledge'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'knowledge'
)\gexec

\connect knowledge

CREATE TABLE IF NOT EXISTS kb_documents (
    id SERIAL PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,             -- mitre_attack / attack_patterns / observables / procedures
    title TEXT,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_documents_category ON kb_documents (category);

CREATE TABLE IF NOT EXISTS incident_history (
    id SERIAL PRIMARY KEY,
    incident_id INTEGER,               -- original id from the operational incident_registry database
    source TEXT,
    summary TEXT,
    description TEXT,
    severity TEXT,
    resolution TEXT,
    lessons_learned TEXT,
    raw_payload JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE incident_history
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_incident_history_created_at ON incident_history (created_at);

CREATE TABLE IF NOT EXISTS rag_index_cursors (
    source TEXT PRIMARY KEY,
    last_id BIGINT NOT NULL DEFAULT 0 CHECK (last_id >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_metrics (
    id SERIAL PRIMARY KEY,
    component TEXT NOT NULL,           -- retrieve_agent, triage_agent...
    action TEXT NOT NULL,              -- retrieve, ask, create_incident, close_incident...
    status TEXT NOT NULL DEFAULT 'success', -- success / error
    duration_ms DOUBLE PRECISION,
    incident_id INTEGER REFERENCES incidents (id) ON DELETE SET NULL,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_metrics_component ON agent_metrics (component);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_created_at ON agent_metrics (created_at);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_incident_id ON agent_metrics (incident_id);