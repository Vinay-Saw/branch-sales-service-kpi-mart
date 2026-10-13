#!/usr/bin/env python3
"""
Load CSVs into PostgreSQL kpi_mart schema.
Usage: python load_postgres.py --host localhost --db kpi_demo --user postgres
Requires: psycopg2-binary, and schema.sql already applied.
"""

import argparse
import pandas as pd
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values

DATA = Path(__file__).parent / "data"

TABLES = [
    "dim_branch",
    "dim_employee",
    "dim_customer",
    "dim_vendor",
    "dim_calendar",
    "fact_leads",
    "fact_inquiries",
    "fact_quotations",
    "fact_bookings",
    "fact_units",
    "fact_installation_pos",
    "fact_warranty",
    "fact_amc",
    "fact_repair_orders",
    "fact_incentives",
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--db", default="kpi_demo")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--password", default="postgres")
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=args.host, port=args.port, dbname=args.db,
        user=args.user, password=args.password
    )
    cur = conn.cursor()

    for table in TABLES:
        csv_path = DATA / f"{table}.csv"
        if not csv_path.exists():
            print(f"Skip {table}: file not found")
            continue
        df = pd.read_csv(csv_path)
        cur.execute(f"TRUNCATE TABLE kpi_mart.{table} CASCADE;")
        cols = list(df.columns)
        values = [tuple(None if pd.isna(v) else v for v in row) for row in df.itertuples(index=False)]
        execute_values(
            cur,
            f"INSERT INTO kpi_mart.{table} ({','.join(cols)}) VALUES %s",
            values
        )
        print(f"Loaded {len(df):,} rows into kpi_mart.{table}")

    conn.commit()
    cur.close()
    conn.close()
    print("Load complete.")

if __name__ == "__main__":
    main()
