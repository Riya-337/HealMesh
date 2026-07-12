-- HealMesh — Postgres Schema
-- Migration: 001_init
-- Append-only enforced at BOTH application level AND database level (triggers).

BEGIN;

CREATE SCHEMA IF NOT EXISTS healmesh;

-- incidents table
CREATE TABLE healmesh.incidents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pod_name        TEXT NOT NULL,
    namespace       TEXT NOT NULL,
    failure_type    TEXT NOT NULL CHECK (failure_type IN (
                        'CrashLoopBackOff', 'OOMKilled', 'ImagePullBackOff',
                        'FailedRollout', 'ResourceQuotaExceeded'
                    )),
    raw_payload     JSONB NOT NULL,
    detected_at     TIMESTAMPTZ NOT NULL
);

-- diagnoses table
CREATE TABLE healmesh.diagnoses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    incident_id     UUID NOT NULL REFERENCES healmesh.incidents(id),
    root_cause      TEXT NOT NULL,
    confidence      TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    suggested_manual_command TEXT,
    raw_llm_response JSONB NOT NULL,
    prompt_snapshot  TEXT NOT NULL,
    llm_model        TEXT NOT NULL,
    latency_ms       INTEGER
);

-- actions table
CREATE TABLE healmesh.actions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    diagnosis_id    UUID NOT NULL REFERENCES healmesh.diagnoses(id),
    action_type     TEXT NOT NULL CHECK (action_type IN (
                        'PATCH', 'REDEPLOY', 'SCALE', 'HELM_UPGRADE', 'NONE'
                    )),
    action_params   JSONB,
    parse_status    TEXT NOT NULL CHECK (parse_status IN ('parsed_ok', 'parse_failed', 'not_suggested'))
);

-- approvals table (Phase 2+)
CREATE TABLE healmesh.approvals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action_id       UUID NOT NULL REFERENCES healmesh.actions(id),
    decision        TEXT NOT NULL CHECK (decision IN ('approved', 'rejected', 'expired')),
    approver_id     TEXT NOT NULL,
    approver_name   TEXT,
    decided_at      TIMESTAMPTZ NOT NULL
);

-- executions table (Phase 2+)
CREATE TABLE healmesh.executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approval_id     UUID NOT NULL REFERENCES healmesh.approvals(id),
    status          TEXT NOT NULL CHECK (status IN ('pending', 'executing', 'succeeded', 'failed', 'rolled_back')),
    pre_action_snapshot JSONB,
    post_action_snapshot JSONB,
    health_check_result TEXT,
    rollback_triggered  BOOLEAN DEFAULT FALSE,
    error_message       TEXT,
    completed_at        TIMESTAMPTZ
);

-- APPEND-ONLY TRIGGERS
-- Blocks UPDATE and DELETE at the database level on ALL audit tables.
CREATE OR REPLACE FUNCTION healmesh.deny_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only. UPDATE and DELETE are not permitted. '
        'Corrections must be made via a new compensating record. '
        'Attempted operation: % on row id=%',
        TG_TABLE_NAME, TG_OP, OLD.id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'healmesh.incidents',
        'healmesh.diagnoses',
        'healmesh.actions',
        'healmesh.approvals',
        'healmesh.executions'
    ] LOOP
        EXECUTE format(
            'CREATE TRIGGER enforce_append_only
             BEFORE UPDATE OR DELETE ON %s
             FOR EACH ROW EXECUTE FUNCTION healmesh.deny_mutation()',
            t
        );
    END LOOP;
END;
$$;

-- Indexes
CREATE INDEX ON healmesh.incidents (namespace, created_at DESC);
CREATE INDEX ON healmesh.incidents (failure_type, created_at DESC);
CREATE INDEX ON healmesh.diagnoses (incident_id);
CREATE INDEX ON healmesh.actions (diagnosis_id);
CREATE INDEX ON healmesh.approvals (action_id);
CREATE INDEX ON healmesh.executions (approval_id);
CREATE UNIQUE INDEX ON healmesh.executions (approval_id) WHERE status = 'executing';

COMMIT;
