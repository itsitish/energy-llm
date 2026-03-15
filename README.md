# energy-llm

Energy expert LLM: insights from your usage data (peak times, tariff recs, schedule optimisation).  
Start with your data; later scale to 100s of homes.

## Setup

```bash
cd energy-llm && pip install -r requirements.txt
```

## Data (your home)

Put your clean CSVs in `data/cleaned/`:

- `electricity.csv` – timestamp, kwh (half-hourly)
- `humidity.csv` – timestamp, humidity_percent
- `internal_temp.csv` – timestamp, temperature_celsius
- `weather.csv` – timestamp + weather columns (optional)

Paths are set in `config.py`. To refresh humidity from DynamoDB: `AWS_PROFILE=your-profile python scripts/export_humidity_from_dynamo.py`.

## Run insights

```bash
python run_insights.py
```

Outputs: peak usage times, tariff recommendation, and a simple schedule suggestion.  
Add your CSV paths in `config.py` when you have data.
