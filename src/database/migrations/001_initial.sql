-- CISCO-EN CLI Mapping Agent — Initial Schema
-- Run against Railway PostgreSQL (pgvector enabled)

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── Main CLI Mappings Table ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cli_mappings (
    id                  SERIAL PRIMARY KEY,

    -- Classification
    tag                 VARCHAR(20) NOT NULL,
    functional_intent   TEXT NOT NULL,

    -- Cisco OS columns
    cisco_ios           TEXT DEFAULT '',
    cisco_iosxe         TEXT DEFAULT '',
    cisco_nxos          TEXT DEFAULT '',

    -- Extreme Networks OS columns
    extreme_exos        TEXT DEFAULT '',
    extreme_voss        TEXT DEFAULT '',
    extreme_slxos       TEXT DEFAULT '',

    -- Negation / undo forms
    negation_cisco      TEXT DEFAULT '',
    negation_en         TEXT DEFAULT '',

    -- Context & provenance
    notes               TEXT DEFAULT '',
    source_ref          VARCHAR(255) DEFAULT '',
    page_ref            VARCHAR(100) DEFAULT '',

    -- RAG vector embedding (all-MiniLM-L6-v2 = 384 dims)
    embedding           vector(384),

    -- Quality tracking
    confidence          FLOAT DEFAULT 1.0,
    is_verified         BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON COLUMN cli_mappings.tag IS
    'Functional bin: [ONBOARD],[SEC-ID],[SYS-INFO],[IF-PHYS],[L2-SEG],[FAB-SDN],[L3-VIRT],[DIAG-LOG],[MGMT-OPS]';
COMMENT ON COLUMN cli_mappings.confidence IS
    '1.0=verified from source, 0.8=PDF-extracted, 0.5=AI-inferred';
COMMENT ON COLUMN cli_mappings.embedding IS
    'Vector from all-MiniLM-L6-v2 on functional_intent text';

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_cli_tag
    ON cli_mappings(tag);

CREATE INDEX IF NOT EXISTS idx_cli_intent_trgm
    ON cli_mappings USING gin(functional_intent gin_trgm_ops);

-- Vector index: ivfflat (approximate nearest neighbour, fast)
-- lists = 100 is appropriate for up to ~1M rows; adjust upward as rows grow
CREATE INDEX IF NOT EXISTS idx_cli_embedding
    ON cli_mappings USING ivfflat(embedding vector_cosine_ops)
    WITH (lists = 100);

-- ── Extraction Tracking ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS extraction_runs (
    id              SERIAL PRIMARY KEY,
    source_type     VARCHAR(20) NOT NULL,    -- csv | pdf | web_crawl | ai_fill
    source_name     VARCHAR(255) NOT NULL,
    rows_added      INTEGER DEFAULT 0,
    rows_updated    INTEGER DEFAULT 0,
    started_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at    TIMESTAMP WITH TIME ZONE,
    status          VARCHAR(20) DEFAULT 'running',  -- running | completed | failed
    error_message   TEXT
);

-- ── Query Analytics Log ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS query_log (
    id                  SERIAL PRIMARY KEY,
    query_text          TEXT NOT NULL,
    tag_filter          VARCHAR(20),
    os_filter           VARCHAR(30),
    results_count       INTEGER,
    top_similarity      FLOAT,
    response_time_ms    INTEGER,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── Web Crawler State ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS crawler_urls (
    id              SERIAL PRIMARY KEY,
    url             TEXT UNIQUE NOT NULL,
    os_target       VARCHAR(30),             -- which OS column this URL serves
    last_crawled    TIMESTAMP WITH TIME ZONE,
    status          VARCHAR(20) DEFAULT 'pending',  -- pending | crawled | error | skipped
    rows_produced   INTEGER DEFAULT 0,
    http_status     INTEGER,
    error_message   TEXT
);

-- ── Auto-update updated_at ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_cli_mappings_updated_at
    BEFORE UPDATE ON cli_mappings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
