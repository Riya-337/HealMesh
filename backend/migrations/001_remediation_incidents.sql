-- Optional Phase 2: persistent remediation history for dashboards / audits.
-- MVP uses n8n Executions only. Apply against a DB *other than* n8n's internal DB
-- if you want isolation (e.g. new DB `prism_remediation` on the same Postgres server).

CREATE TABLE IF NOT EXISTS remediation_incidents (
  id BIGSERIAL PRIMARY KEY,
  incident_id UUID NOT NULL UNIQUE,
  schema_version TEXT NOT NULL DEFAULT '1.0',
  status TEXT NOT NULL DEFAULT 'received',
  source_payload JSONB NOT NULL,
  openclaw_response JSONB,
  remediation_action TEXT,
  outcome TEXT,
  error_detail TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_remediation_incidents_created_at
  ON remediation_incidents (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_remediation_incidents_status
  ON remediation_incidents (status);
