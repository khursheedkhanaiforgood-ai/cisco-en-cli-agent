# CISCO-EN CLI Mapping Agent — Claude Code Guide

## Project Purpose
RAG-powered web app that translates CLI commands across **6 network OSes** (Cisco IOS, IOS-XE, NX-OS + Extreme EXOS, VOSS, SLX-OS) organized into **9 functional bins**. Deployed on Railway with PostgreSQL + pgvector.

## Architecture
```
src/
  config.py              — All env vars, tag/OS definitions, constants
  agents/
    orchestrator.py      — Master agent: classify → RAG search → Claude API
    prompts/
      system_master.md   — Claude system prompt with platform differences
  database/
    connection.py        — SQLAlchemy engine, get_session(), init_db()
    models.py            — CLIMapping, ExtractionRun, QueryLog, CrawlerURL
    seed.py              — Orchestrates CSV load + PDF extraction
    migrations/
      001_initial.sql    — pgvector extension, cli_mappings table, IVFFlat index
  embeddings/
    encoder.py           — sentence-transformers all-MiniLM-L6-v2, encode/encode_batch
  rag/
    search.py            — pgvector cosine similarity search, keyword fallback, get_stats
  extractors/
    csv_loader.py        — Load seed CSVs → DB with embeddings
    pdf_extractor.py     — pdfplumber: monospace font detection → CLI extraction
  ui/
    app.py               — Streamlit entry point: 11 tabs (AI Query + 9 bins + DB Browser)
    components/
      query_box.py       — NL query input → orchestrator → formatted response
      bin_tabs.py        — Per-tag filterable table with download
      db_browser.py      — Full search, stats, re-seed admin
data/
  seed/                  — 9 CSV files (~500 rows), one per functional bin
  extracted/             — PDF extraction output JSONs
```

## Critical Domain Knowledge

### 6 OS Columns
| Column | Platform |
|--------|----------|
| cisco_ios | Cisco IOS classic |
| cisco_iosxe | Cisco IOS-XE 17.x (Catalyst 9000) |
| cisco_nxos | Cisco NX-OS 10.x (Nexus) |
| extreme_exos | ExtremeXOS / Switch Engine 33.x |
| extreme_voss | VOSS / Fabric Engine 9.x |
| extreme_slxos | SLX-OS 20.x |

### Platform Differences (ALWAYS flag these)
1. **NX-OS feature prerequisite**: `feature <protocol>` required before configuring OSPF, BGP, LLDP, etc.
2. **EXOS verb-noun flat syntax**: `configure vlan <name> add ports <p> tagged` — no modal interface sub-mode
3. **VOSS I-SID**: Layer 2 segmentation via `vlan i-sid <vlanid> <isid>` for Fabric Connect
4. **Negation**: Cisco `no <cmd>` → EXOS `unconfigure`/`disable` → VOSS `no` (same as Cisco)
5. **VOSS ZTF**: `auto-sense enable` → IS-IS/SPBM fabric auto-builds. No Cisco equivalent.
6. **EXOS OSPF**: VLAN-based (`configure ospf add vlan <name> area <id>`) vs Cisco interface-based

### 9 Functional Bins
[ONBOARD] [SEC-ID] [SYS-INFO] [IF-PHYS] [L2-SEG] [FAB-SDN] [L3-VIRT] [DIAG-LOG] [MGMT-OPS]

## Setup

```bash
cp .env.example .env        # Add ANTHROPIC_API_KEY and DATABASE_URL
pip install -r requirements.txt
python -m src.database.seed              # Load ~500 seed rows
python -m src.database.seed --pdf        # + PDF extraction (~3000 more rows)
streamlit run src/ui/app.py
```

## Railway Deployment
- PostgreSQL plugin provides `DATABASE_URL` automatically
- Add `ANTHROPIC_API_KEY` in Railway variables
- Start command: `streamlit run src/ui/app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
- Run seed after first deploy: `python -m src.database.seed`

## Key Files
- `src/config.py` — change model, embedding dim, similarity threshold here
- `data/seed/*.csv` — 9 CSV files, ~500 rows (grow to 12K via PDF + web crawler)
- `src/database/migrations/001_initial.sql` — IVFFlat index with lists=100
- `src/agents/prompts/system_master.md` — Claude's system prompt

## Data Growth Plan
1. Seed CSVs: ~500 rows (done)
2. PDF extraction (VOSS 8.9, EXOS 22.7): +3,000-4,000 rows
3. Web crawler (Extreme docs sites): +5,000+ rows
4. AI gap-filling for cross-OS mappings: fill blanks in existing rows

## Patterns & Conventions
- All DB access via `get_session()` context manager — never raw connections
- Embeddings always generated in batch via `encode_batch()` — never one-by-one
- Tag values include brackets: `[ONBOARD]` not `ONBOARD`
- Empty OS commands: empty string `""` not `"N/A"` or `"—"`
- Similarity threshold 0.35 — lower than typical because CLI queries are short/terse

---

*© 2026 Khursheed Khan. All rights reserved. | CISCO-EN CLI Mapping Agent | March 31, 2026*
