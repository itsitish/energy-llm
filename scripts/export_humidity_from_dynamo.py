"""
Export humidity from DynamoDB to CSV.

DynamoDB shape: PK = LocationId:Commodity, item has "Readings" = { "YYYY-MM-DD": { "unix_ts_str": value }, ... }.
Flattens to CSV: timestamp, humidity_percent.
Uses Query on partition key (no Scan).
"""
import csv
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

try:
    import boto3
except ImportError:
    boto3 = None

# Config: set env or edit defaults
TABLE_NAME = os.environ.get("DYNAMODB_HUMIDITY_TABLE", "CadReading")
REGION = os.environ.get("AWS_REGION", "eu-west-2")
# Partition key value for this device's humidity (LocationId:Commodity)
PK_VALUE = os.environ.get("DYNAMODB_HUMIDITY_PK", "53f09efc-2c99-44b0-8392-5540766e7048:humidity")
OUTPUT_CSV = Path(__file__).resolve().parent.parent / "data" / "raw" / "humidity.csv"

def _float_val(v):
    """Convert DynamoDB Number (Decimal) or float to float."""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ts_to_datetime(ts_str):
    """Parse timestamp string (Unix seconds or ms) to UTC datetime."""
    try:
        n = int(ts_str)
    except (ValueError, TypeError):
        return None
    # If > 1e12 assume milliseconds
    if n > 1e12:
        n = n // 1000
    try:
        return datetime.fromtimestamp(n, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def flatten_readings(readings):
    """
    Flatten Readings map to list of (datetime, humidity).
    readings: { "date": { "unix_ts_str": value }, ... }
    """
    rows = []
    if not isinstance(readings, dict):
        return rows
    for _date_key, day_map in readings.items():
        if not isinstance(day_map, dict):
            continue
        for ts_str, val in day_map.items():
            dt = _ts_to_datetime(ts_str)
            fval = _float_val(val)
            if dt is not None and fval is not None:
                rows.append((dt, fval))
    return rows


def query_and_export(
    table_name: str = TABLE_NAME,
    region: str = REGION,
    pk_value: str = PK_VALUE,
    out_path: Path = OUTPUT_CSV,
) -> int:
    """Query by partition key (LocationId:Commodity), flatten Readings, write CSV. Returns row count."""
    if boto3 is None:
        raise RuntimeError("Install boto3: pip install boto3")

    dynamo = boto3.resource("dynamodb", region_name=region)
    table = dynamo.Table(table_name)
    pk_attr = "LocationId:Commodity"
    all_rows = []
    kwargs = {
        "KeyConditionExpression": "#pk = :pkval",
        "ExpressionAttributeNames": {"#pk": pk_attr},
        "ExpressionAttributeValues": {":pkval": pk_value},
    }
    while True:
        resp = table.query(**kwargs)
        for item in resp.get("Items", []):
            readings = item.get("Readings", item)
            all_rows.extend(flatten_readings(readings))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key

    all_rows.sort(key=lambda x: x[0])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "humidity_percent"])
        for dt, val in all_rows:
            w.writerow([dt.isoformat(), val])
    return len(all_rows)


def main():
    n = query_and_export()
    print(f"Wrote {n} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
