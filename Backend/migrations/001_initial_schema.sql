-- ResQNet disaster call management — normalized Postgres schema
-- Run against Supabase Postgres or any PostgreSQL 14+ database.

-- ---------------------------------------------------------------------------
-- Types
-- ---------------------------------------------------------------------------
CREATE TYPE priority_level AS ENUM ('critical', 'high', 'medium', 'low');
CREATE TYPE sentiment_label AS ENUM ('positive', 'neutral', 'negative');
CREATE TYPE incident_source AS ENUM ('telegram', 'web', 'api');

-- ---------------------------------------------------------------------------
-- Callers (optional identity for repeat reporters)
-- ---------------------------------------------------------------------------
CREATE TABLE callers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name    TEXT NOT NULL,
    telegram_user_id BIGINT UNIQUE,
    phone           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_callers_telegram_user_id ON callers (telegram_user_id)
    WHERE telegram_user_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Incidents (dashboard-facing row — denormalized for realtime UI)
-- ---------------------------------------------------------------------------
CREATE TABLE incidents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caller_id       UUID REFERENCES callers (id) ON DELETE SET NULL,
    caller_name     TEXT NOT NULL,
    location        TEXT NOT NULL,
    source          incident_source NOT NULL DEFAULT 'web',
    priority        priority_level NOT NULL DEFAULT 'low',
    sentiment       sentiment_label,
    urgency         REAL CHECK (urgency IS NULL OR (urgency >= 0 AND urgency <= 1)),
    stress          REAL CHECK (stress IS NULL OR (stress >= 0 AND stress <= 1)),
    frustration     REAL CHECK (frustration IS NULL OR (frustration >= 0 AND frustration <= 1)),
    transcript      TEXT,
    action_items    TEXT,
    summary         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_incidents_created_at ON incidents (created_at DESC);
CREATE INDEX idx_incidents_priority ON incidents (priority);
CREATE INDEX idx_incidents_caller_id ON incidents (caller_id);

-- ---------------------------------------------------------------------------
-- Transcript (1:1 with incident — Valsea STT output)
-- ---------------------------------------------------------------------------
CREATE TABLE transcripts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id         UUID NOT NULL UNIQUE REFERENCES incidents (id) ON DELETE CASCADE,
    raw_text            TEXT NOT NULL,
    clarified_text      TEXT,
    detected_languages    TEXT[],
    semantic_tags       JSONB,
    valsea_model        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Voice analysis (1:1 — Valsea prosody)
-- ---------------------------------------------------------------------------
CREATE TABLE voice_analyses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id         UUID NOT NULL UNIQUE REFERENCES incidents (id) ON DELETE CASCADE,
    frustration         REAL CHECK (frustration >= 0 AND frustration <= 1),
    stress              REAL CHECK (stress >= 0 AND stress <= 1),
    politeness          REAL CHECK (politeness >= 0 AND politeness <= 1),
    hesitation          REAL CHECK (hesitation >= 0 AND hesitation <= 1),
    urgency             REAL CHECK (urgency >= 0 AND urgency <= 1),
    valsea_job_id       TEXT,
    raw_predictions     JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Sentiment analysis (1:1 — Valsea sentiment on transcript)
-- ---------------------------------------------------------------------------
CREATE TABLE sentiment_analyses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL UNIQUE REFERENCES incidents (id) ON DELETE CASCADE,
    sentiment       sentiment_label NOT NULL,
    confidence      REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    emotions        TEXT[],
    reasoning       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Gemini structured extraction (1:1)
-- ---------------------------------------------------------------------------
CREATE TABLE gemini_analyses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL UNIQUE REFERENCES incidents (id) ON DELETE CASCADE,
    model_version   TEXT NOT NULL,
    summary         TEXT,
    suggested_priority priority_level,
    raw_response    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Child rows (1:N from incident)
-- ---------------------------------------------------------------------------
CREATE TABLE incident_topics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    topic           TEXT NOT NULL,
    relevance_score REAL CHECK (relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 1)),
    sort_order      INT NOT NULL DEFAULT 0,
    UNIQUE (incident_id, topic)
);

CREATE INDEX idx_incident_topics_incident_id ON incident_topics (incident_id);

CREATE TABLE incident_key_points (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    point           TEXT NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0
);

CREATE INDEX idx_incident_key_points_incident_id ON incident_key_points (incident_id);

CREATE TABLE incident_action_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    item            TEXT NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    completed       BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX idx_incident_action_items_incident_id ON incident_action_items (incident_id);

-- ---------------------------------------------------------------------------
-- Pipeline audit log (1:N processing steps per incident)
-- ---------------------------------------------------------------------------
CREATE TABLE processing_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    step            TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    detail          TEXT,
    duration_ms     INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_processing_logs_incident_id ON processing_logs (incident_id);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_callers_updated_at
    BEFORE UPDATE ON callers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_incidents_updated_at
    BEFORE UPDATE ON incidents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Dashboard view (joins related tables for admin/reporting)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW incident_details AS
SELECT
    i.id,
    i.caller_name,
    i.location,
    i.source,
    i.priority,
    i.sentiment,
    i.urgency,
    i.stress,
    i.frustration,
    i.transcript,
    i.action_items,
    i.summary,
    i.created_at,
    t.raw_text AS transcript_raw,
    va.politeness,
    va.hesitation,
    sa.confidence AS sentiment_confidence,
    ga.model_version AS gemini_model,
    ga.suggested_priority AS gemini_suggested_priority,
    (
        SELECT COALESCE(json_agg(it.topic ORDER BY it.sort_order), '[]'::json)
        FROM incident_topics it
        WHERE it.incident_id = i.id
    ) AS topics,
    (
        SELECT COALESCE(json_agg(ik.point ORDER BY ik.sort_order), '[]'::json)
        FROM incident_key_points ik
        WHERE ik.incident_id = i.id
    ) AS key_points
FROM incidents i
LEFT JOIN transcripts t ON t.incident_id = i.id
LEFT JOIN voice_analyses va ON va.incident_id = i.id
LEFT JOIN sentiment_analyses sa ON sa.incident_id = i.id
LEFT JOIN gemini_analyses ga ON ga.incident_id = i.id;

-- ---------------------------------------------------------------------------
-- Supabase: RLS + realtime (skipped on plain Postgres without Supabase roles)
-- ---------------------------------------------------------------------------
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE callers ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE $policy$
            CREATE POLICY incidents_select_anon ON incidents
                FOR SELECT TO anon, authenticated
                USING (true)
        $policy$;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        EXECUTE $policy$
            CREATE POLICY incidents_insert_service ON incidents
                FOR INSERT TO service_role
                WITH CHECK (true)
        $policy$;
        EXECUTE $policy$
            CREATE POLICY incidents_all_service ON incidents
                FOR ALL TO service_role
                USING (true)
                WITH CHECK (true)
        $policy$;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE incidents';
    END IF;
END $$;
