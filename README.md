# energy-llm

AI-powered energy advisor: turn household usage data (electricity, temp, humidity, weather) into structured insights and natural-language answers via a local LLM.

---

## Repo summary

| Layer | What |
|-------|-----|
| **Data** | Raw CSVs (mixed resolution) in `data/raw/` → cleaned to half-hourly in `data/cleaned/` |
| **Config** | `config.py` – paths for CSVs, Tigerdata/DynamoDB env vars |
| **Loaders** | `data/loaders.py` – load elec, gas, humidity, temp, weather, home profile from CSV |
| **Clean** | `data/clean_to_halfhourly.py` – resample to 30min, dedupe, fill gaps (elec=0; temp/hum=interp+ffill; weather=ffill) |
| **Pipeline** | `pipeline/hourly.py` – build hourly dataset from cleaned CSVs for insights/LLM |
| **Insights** | `insights/` – peak_usage_times, tariff_recommendation, schedule_suggestion, temperature_summary, humidity_summary |
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
3. **Pipeline** reads `data/cleaned/` (via `config.py`). Insights and notebook use these paths.

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

- **Insights only** (peak times, tariff, schedule):  
  `python run_insights.py`
- **Full flow** (insights + LLM Q&A, plots): open `notebooks/llm.ipynb`, run all. Cell 0 sets path; then build_hourly_dataset, insights, Plotly plots, load model, interactive Q&A.

---

## Layout

```
config.py              # Paths, Tigerdata/Dynamo env
data/
  loaders.py           # Load CSVs to Series/DataFrame
  clean_to_halfhourly.py
  raw/                 # Input CSVs (mixed res)
  cleaned/             # Half-hourly CSVs (pipeline input)
  sql/                 # Tigerdata: elec, internal_temperature, weather_observations
insights/              # peaks, tariff, schedules, temperature, humidity
pipeline/hourly.py     # build_hourly_dataset()
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
- `TIGERDATA_URL`, `DEVICE_ID`, `TIGERDATA_REF_ELEC`, `TIGERDATA_REF_INT_TEMP`, `POSTCODE_DISTRICT` – for Tigerdata.
- DynamoDB: set via env (`DYNAMODB_HUMIDITY_TABLE`, `DYNAMODB_HUMIDITY_PK`).
