---
name: run
description: Start the Streamlit app locally
---

Run the CISCO-EN CLI Mapping Agent:

```bash
cd /Users/khukhan/Projects/cisco-en-cli-agent
streamlit run src/ui/app.py
```

Prerequisite — if first time:
```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY and DATABASE_URL
python -m src.database.seed
```
