# NotebookLM Source Documents

These 14 files are the original Google NotebookLM outputs that were used to:
1. Extract per-functional-bin command tables (9 bin docs)
2. Calibrate the Claude system prompt guardrails (`src/agents/prompts/system_master.md`)
3. Generate 9 per-bin AI guardrail files (`src/agents/prompts/bins/`)
4. Seed thematic rows in the database (`src/database/seed_themes.py`)

## Files

### Per-Bin Command Mapping Tables (primary source)
| File | Functional Bin |
|------|---------------|
| `Onboarding Mapping Table_ [ONBOARD] Functional Group.docx` | [ONBOARD] |
| `[SEC-ID] Functional Group_ ...docx` | [SEC-ID] |
| `[SYS-INFO] Multi-Vendor System Information...docx` | [SYS-INFO] |
| `[IF-PHYS] Physical Interface and Port Access...docx` | [IF-PHYS] |
| `L2 Segmentation [L2-SEG] Command Mapping Reference.docx` | [L2-SEG] |
| `[FAB-SDN] Fabric Setup Mapping Table.docx` | [FAB-SDN] |
| `[FAB-SDN] Fabric Setup Mapping Table-2.docx` | [FAB-SDN] (extended) |
| `[L3-VIRT] Layer 3 and Virtual Routing...docx` | [L3-VIRT] |

### Deep Analysis & Synthesis Documents
| File | Purpose |
|------|---------|
| `NoteBookLLM_CLI_DeepLevelAnalyes.docx` | Cross-bin thematic deep extraction (all 9 volumes) |
| `NotebookLLM_CLI_EndItems.docx` | NX-OS MDP architecture + end-item command lists |
| `Google NotebookLLM_EN-Cisco_CLI - Chat.docx` | Original Q&A chat session with NotebookLM |
| `Master Command Dataset for RAN-Enabled AI Agent Calibration...docx` | Master calibration dataset |
| `Cisco CLI Command Master Index_ NX-OS 10.5(x) & IOS-XE 17.17.x.docx` | Cisco command index |
| `CLI Translation Master Dataset_ Cisco IOS-XE_NX-OS & Extreme Switch Engine_Fabric Engine.docx` | Full translation dataset |

## How These Were Used

The documents were NOT loaded directly into the database. Instead:
- Command syntax was extracted and placed in seed CSVs (`data/seed/*.csv`)
- Architectural rules and guardrails were written into `src/agents/prompts/system_master.md`
- Bin-specific rules are in `src/agents/prompts/bins/bin_*.md`

**Do not delete these files.** They are the ground-truth reference for all guardrail decisions.
If you need to extend or correct the AI's behavior for a specific bin, start here.

---

*© 2026 Khursheed Khan. All rights reserved. | CISCO-EN CLI Mapping Agent | March 31, 2026*
