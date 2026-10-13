-- Simple loader (run after schema.sql)
-- Assumes CSVs are in /tmp/kpi_data/ or adjust paths.
-- For local demo: COPY from local files (superuser) or use \copy in psql.

-- Example with \copy (run from psql, paths adjusted):
-- \copy kpi_mart.dim_branch FROM 'data/dim_branch.csv' CSV HEADER;
-- \copy kpi_mart.dim_product FROM 'data/dim_product.csv' CSV HEADER;
-- \copy kpi_mart.dim_salesperson FROM 'data/dim_salesperson.csv' CSV HEADER;
-- \copy kpi_mart.dim_customer FROM 'data/dim_customer.csv' CSV HEADER;
-- \copy kpi_mart.dim_calendar FROM 'data/dim_calendar.csv' CSV HEADER;
-- \copy kpi_mart.fact_bookings FROM 'data/fact_bookings.csv' CSV HEADER;
-- \copy kpi_mart.fact_installations FROM 'data/fact_installations.csv' CSV HEADER;
-- \copy kpi_mart.fact_service_calls FROM 'data/fact_service_calls.csv' CSV HEADER;
-- \copy kpi_mart.fact_targets FROM 'data/fact_targets.csv' CSV HEADER;
-- \copy kpi_mart.fact_amc FROM 'data/fact_amc.csv' CSV HEADER;

-- Or Python loader (see load_postgres.py)
