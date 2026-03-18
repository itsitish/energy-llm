# energy-llm

AI-powered energy advisor: turn household usage + device profile data (electricity, temp, humidity, weather, home device fuels) into structured insights and natural-language answers via a local LLM.

---

## Repo summary

| Layer | What |
|-------|-----|
| **Data** | Raw CSVs (mixed resolution) in `data/raw/` → cleaned to half-hourly in `data/cleaned/` |
| **Config** | `config.py` – paths for CSVs, Tigerdata/DynamoDB env vars |
| **Loaders** | `data/loaders.py` – load elec, gas, humidity, temp, weather, home profile from CSV |
| **Clean** | `data/clean_to_halfhourly.py` – resample to 30min, dedupe, fill gaps (elec=0; temp/hum=interp+ffill; weather=ffill) |
| **Insights** | `insights/` – peak_usage_times, tariff_recommendation, schedule_suggestion, temperature_summary, humidity_summary (+ a richer `build_household_context`) |
| **LLM** | `notebooks/llm.ipynb` – load model (Qwen2.5-1.5B), format context from insights, interactive Q&A |
| **Scripts** | Extract from Tigerdata or DynamoDB → raw; run clean → cleaned |

---

## Setup

```bash
cd energy-llm && pip install -r requirements.txt
```

Optional: `sqlalchemy` + `psycopg2-binary` for Tigerdata; AWS profile for DynamoDB.

---

## Data flow

1. **Raw** (`data/raw/`): electricity (half-hourly), humidity (minutely), internal_temp, weather (hourly). Put CSVs here or pull via scripts.
2. **Clean**: `python scripts/run_clean_to_halfhourly.py` → writes half-hourly CSVs to `data/cleaned/`.
3. **Use**: insights + notebook read `data/cleaned/` (via `config.py`).

---

## Data sources

- **Manual**: Copy CSVs into `data/raw/`, then run the clean script.
- **Tigerdata**: Set `TIGERDATA_URL`, `DEVICE_ID` (or `TIGERDATA_REF_ELEC`, `TIGERDATA_REF_INT_TEMP`, `POSTCODE_DISTRICT`). SQLs in `data/sql/` (elec.sql, internal_temperature.sql, weather_observations.sql).  
  `python scripts/extract_from_tigerdata.py` → writes to `data/raw/`.
- **DynamoDB**: Set `AWS_PROFILE`, `DYNAMODB_HUMIDITY_TABLE`, `DYNAMODB_HUMIDITY_PK`.  
  `python scripts/export_humidity_from_dynamo.py` → writes `data/raw/humidity.csv`.

After any extract, run `python scripts/run_clean_to_halfhourly.py`.

---

## Run

- **Insights only** (peak times, tariff, schedule + home-profile implications):  
  `python run_insights.py`
- **Full flow** (insights + LLM Q&A, plots): open `notebooks/llm.ipynb`, run all (auto-cleans if needed → builds insights/context → runs golden evals → plots → model → interactive Q&A).
  - Note: the notebook reads **cleaned half-hourly CSVs directly**; it does not build an hourly dataset.

### `notebooks/llm.ipynb` in one glance

The notebook is the single end-to-end entry point for recruiters/jobs:

- Loads/auto-creates `data/cleaned/*.csv` if missing
- Builds `insight_text` using electricity + indoor temp + indoor humidity + external weather + `data/cleaned/home_profile.csv`
- Runs **golden evals** (`evals/golden_qa.jsonl`) before letting you ask questions
- Shows sanity-check Plotly charts (including `Cost (£)` under your tariff)
- Starts an interactive Q&A UI that enforces a strict grounded output format

---
## Tariff configuration (notebook)

Electricity cost + tariff impact are computed in `notebooks/llm.ipynb` using the `TARIFF` dict in the LLM context cell.

To change time windows, edit:
- `TARIFF["offpeak_windows"]` (e.g. `["02:00-05:00"]`)
- `TARIFF["peak_windows"]` (e.g. `["16:00-19:00"]`)

The cost line and the “TARIFF IMPACT” section in the LLM context will update automatically.

---
## Evals (golden Q&A)

Run a small groundedness/consistency harness over a golden set of questions:

```bash
python evals/run_evals.py
```

The eval runner expects the assistant to follow a strict output format:
- `Answer: ...`
- `Evidence: ...`

If the answer is not explicitly present in the provided context, it must reply exactly:
`Not enough data in context to answer.`

---

## Layout

```
config.py              # Paths, Tigerdata/Dynamo env
data/
  loaders.py           # Load CSVs to Series/DataFrame
  clean_to_halfhourly.py
  raw/                 # Input CSVs (mixed res)
  cleaned/             # Half-hourly CSVs (pipeline input) + `home_profile.csv`
  sql/                 # Tigerdata: elec, internal_temperature, weather_observations
insights/              # peaks, tariff, schedules, temperature, humidity
notebooks/llm.ipynb    # LLM + plots + Q&A
scripts/
  run_clean_to_halfhourly.py
  extract_from_tigerdata.py
  export_humidity_from_dynamo.py
run_insights.py
requirements.txt
```

---

## Config (`config.py`)

- `RAW_DIR`, `CLEANED_DIR` – data folders.
- `ELECTRICITY_CSV`, `HUMIDITY_CSV`, `TEMPERATURE_CSV`, `WEATHER_CSV` – point to `data/cleaned/` files.
- `HOME_PROFILE_CSV` – points to `data/cleaned/home_profile.csv` (device fuels + estimated annual consumption; supports both numeric 1/0 and string labels like `elec`/`gas`).
- `TIGERDATA_URL`, `DEVICE_ID`, `TIGERDATA_REF_ELEC`, `TIGERDATA_REF_INT_TEMP`, `POSTCODE_DISTRICT` – for Tigerdata.
- DynamoDB: set via env (`DYNAMODB_HUMIDITY_TABLE`, `DYNAMODB_HUMIDITY_PK`).
