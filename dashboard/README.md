# KPI dashboard

A six-tab dashboard (Overview, Sales, Installation, Service, People & targets, Data notes) with a branch filter, built on the CSVs in `data/`.

- `build_dashboard_data.py` aggregates `data/*.csv` into `dashboard/data/*.json` and generates every finding sentence from the same numbers. Run it from the repo root after the data changes: `python dashboard/build_dashboard_data.py`.
- `index.html` is the page source of the hosted dashboard. It reads the JSON files as named datasets through the dashboard host's `dash` API and draws with d3, so it does not run as a standalone file.

Conventions: the as-of date is the latest lead, booking or repair-order date; "year to date" runs to the last complete month and is compared with the same months a year earlier. Branch sales target is the sum of Salesperson targets; installation target is the sum of Installation Engineer targets. Dataset is simulated.
