# Base Material — Source Reference Documents

These are the primary source documents that formed the foundation of the CISCO-EN CLI Mapping Agent.
They pre-date the NotebookLM analysis and represent the raw input that was researched, curated,
and fed into the Google NotebookLM pipeline.

## Files

| File | Type | Description |
|------|------|-------------|
| `CISCO_EN_Commands_Mar 31 2026.docx` | DOCX | Direct Cisco ↔ Extreme CLI command comparison compiled March 31 2026 |
| `CLI_X-Ref_Guide_1.0-3.pdf` | PDF | CLI Cross-Reference Guide v1.0 — multi-platform command mapping |
| `EXOS-Layer2-Lab-Guide-Shareable.html` | HTML | EXOS Layer 2 lab guide (shareable version, EVE-NG labs) |
| `Extreme XOS User Guide 22.7.pdf` | PDF | Official Extreme XOS / Switch Engine User Guide v22.7 (43 MB) |
| `Google NotebookLLM_EN-Cisco_CLI - Chat.docx` | DOCX | Full Google NotebookLM chat session — EN/Cisco CLI Q&A |
| `Google_Search_EN-CISCO_Config_March 31 2026_10am.docx` | DOCX | Google search research session — EN/Cisco config commands |
| `Network_CLI_Cheat_Sheet 1.docx` | DOCX | Multi-vendor CLI cheat sheet reference |
| `NotebookLLM_CLI_EndItems.docx` | DOCX | NotebookLM end-item synthesis — NX-OS MDP + command summaries |
| `VOSSUserGuide_9.0_UG.pdf` | PDF | Official Extreme VOSS / Fabric Engine User Guide v9.0 (38 MB) |

## Research Pipeline

These files were used in the following order:

```
1. Google Research
   └─► CLI_X-Ref_Guide_1.0-3.pdf
   └─► Network_CLI_Cheat_Sheet 1.docx
   └─► Google_Search_EN-CISCO_Config_March 31 2026_10am.docx
   └─► CISCO_EN_Commands_Mar 31 2026.docx

2. Google NotebookLM (uploaded vendor docs + research outputs)
   └─► Extreme XOS User Guide 22.7.pdf         ← primary EXOS source
   └─► VOSSUserGuide_9.0_UG.pdf               ← primary VOSS source
   └─► Google NotebookLLM_EN-Cisco_CLI - Chat.docx  ← Q&A session output
   └─► NotebookLLM_CLI_EndItems.docx          ← synthesized end items

3. Claude Code (architecture + development)
   └─► NotebookLM outputs → 9 per-bin seed CSVs → PostgreSQL + pgvector
   └─► Vendor doc rules → src/agents/prompts/system_master.md
   └─► Per-bin analysis → src/agents/prompts/bins/bin_*.md
```

## Important Notes

- The two large PDFs (EXOS User Guide 22.7 + VOSS User Guide 9.0) are the authoritative
  vendor references. They are the source of truth for any command verification.
- These PDFs are also the input for the PDF extraction pipeline:
  `python -m src.database.seed --pdf`
  which will parse them and add ~3,000–4,000 additional rows to the database.
- The HTML lab guide (`EXOS-Layer2-Lab-Guide-Shareable.html`) is a hands-on reference
  for Switch Engine Layer 2 configuration patterns.

---

*© 2026 Khursheed Khan. All rights reserved. | CISCO-EN CLI Mapping Agent | March 31, 2026*
