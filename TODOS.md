# TODOS

## Cortex v3 — GridLedger AI Financial Intelligence System

### settings.py duplication bug
**What:** `config/settings.py` contains two complete module definitions. First block
lacks dotenv. Second block has it. Both execute on import.
**Why:** Not a runtime crash (mkdir uses exist_ok=True, load_dotenv runs once) but
confusing to anyone reading the file. Will cause confusion during the rewrite.
**How to fix:** Consolidate into one block, dotenv loaded at top.
**Depends on:** Part of build step 0 (settings.py rewrite).
**Context:** Introduced when dotenv support was added to an existing file without
removing the original definitions. Low urgency — fix during Cortex rewrite.
