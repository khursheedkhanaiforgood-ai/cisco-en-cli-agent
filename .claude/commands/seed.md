---
name: seed
description: Seed the database with CLI mapping data
---

Seed the PostgreSQL database with CLI command mappings:

```bash
# Load ~500 seed rows from CSV files
python -m src.database.seed

# Load seed CSVs + extract from local PDF files (~3000+ rows)
python -m src.database.seed --pdf

# Force overwrite existing rows
python -m src.database.seed --overwrite
```

PDF paths expected:
- `/Users/khukhan/Downloads/VOSSUserGuide_8.9_UG.pdf`
- `/Users/khukhan/Downloads/Extreme XOS User Guide 22.7.pdf`
