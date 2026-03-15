# energy-llm

Energy expert LLM: insights from your usage data (peak times, tariff recs, schedule optimisation).  
Start with your data; later scale to 100s of homes.

## Setup

```bash
cd energy-llm && pip install -r requirements.txt
```

## Data (your home)

**Raw data** (mixed resolution) goes in `data/raw/`:

- `electricity.csv` – half-hourly: timestamp, kwh
- `humidity.csv` – minutely: timestamp, humidity_percent
- `internal_temp.csv` – timestamp, temperature_celsius
- `weather.csv` – hourly: timestamp + weather columns (optional)

**Clean to half-hourly** (resample 30T, drop duplicates, fill gaps):

```bash
python scripts/run_clean_to_halfhourly.py
```

Writes to `data/cleaned/`. Filling: elec gaps = 0; humidity/temp = time interpolation + ffill/bfill; weather = ffill.

**Option A – place files in raw**  
Copy or export your CSVs into `data/raw/`, then run the command above.

**Option B – Tigerdata**  
Extract writes to `data/raw/`; then run the clean script:

```bash
export TIGERDATA_URL=postgresql://user:pass@host/db
export DEVICE_ID=your_ref
python scripts/extract_from_tigerdata.py
python scripts/run_clean_to_halfhourly.py
```

**Option C – humidity from DynamoDB**  
Export writes to `data/raw/humidity.csv`; then run the clean script:

```bash
export AWS_PROFILE=your-profile
python scripts/export_humidity_from_dynamo.py
python scripts/run_clean_to_halfhourly.py
```

## Run insights

```bash
python run_insights.py
```

Outputs: peak usage times, tariff recommendation, and a simple schedule suggestion.
