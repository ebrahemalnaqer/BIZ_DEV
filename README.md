# BizPilot AI (MVP)
Local-first cost-intelligence app for small cafés/restaurants. **Rule-based analytics, not an AI model.** No API keys needed.

## Setup (Windows PowerShell)
```
cd BizPilot_AI_New
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
## Tests
`python -m unittest discover -s tests -v`

## Using it
Upload a .csv/.xlsx on Overview → check what was understood → answer any question → confirm. Demo data is shown until you confirm. Budget files use columns `category,month,budget` (template download in Budget). Sample: `sample_data/messy_sample.csv`.

## Architecture
`smart_import.py` (import) · `expense_engine.py` (alerts, unit cost) · `budget_engine.py` · `investigation_store.py` (SQLite) · `export_reports.py` · `app.py` (UI only) · `demo_data.py` (synthetic).

## Limitations
Long format only (one row per date/category; no wide category-per-column layouts). No repeated-subscription detection yet. Streamlit UI (Arabic RTL, flows) not yet exercised in a browser. Tested only on synthetic files; real-file accuracy is unvalidated. Not an accounting system.
