# Branch Sales & Service KPI Mart

**Dataset is simulated.** Questions are the ones branch leadership actually asks.  
No real company names or personal details.

Three branches: **Surat, Vadodara, Vapi**.

## What this is

One Power BI model fed by PostgreSQL. Facts: bookings, installations, service calls (+ targets and AMC).  
Dimensions: calendar (role-playing), branch, salesperson, product (gearless / hydraulic / home lift), customer.

Leadership page answers:  
**“Which branch is off target, and is it a sales problem or a delivery problem?”**

## Stack

- PostgreSQL (star schema)
- Python loader (`load_postgres.py`)
- Power BI + DAX + Power Query
- No new frameworks

## Quick start

1. Create database and run `sql/schema.sql`.
2. Generate data: `python generate_data.py` (already run; CSVs in `data/`).
3. Load: `python load_postgres.py --db yourdb ...` (requires psycopg2).
4. Connect Power BI to the schema. Relationships and measures in `docs/dax_measures.md`.
5. Build three pages: Sales, Delivery, Service. One North Star each.
6. Add a reconciliation visual that proves dashboard total = SQL total.

## Key files

- `data/` — synthetic ERP extracts (CSV)
- `sql/schema.sql` — star schema
- `docs/metric_dictionary.md` — what “booking” includes/excludes
- `docs/requirement_note.md` — stakeholder question
- `docs/erp_boundary.md` — nightly export boundary and ugly cases
- `docs/dax_measures.md` — time intelligence, gap-to-target, ageing

## Ugly cases included

- Cancelled bookings still in the pipeline
- Targets that change mid-quarter
- Service calls opened in one branch and closed in another

## Do not claim

Any rupee impact measured at a real employer. This is a simulated dataset demonstrating the model and the questions.
