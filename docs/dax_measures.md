# DAX Measures (Power BI)

Connect to PostgreSQL kpi_mart schema. Create relationships:

- fact_bookings[booking_date] → dim_calendar[full_date] (active)
- fact_installations[scheduled_date] → dim_calendar[full_date] (inactive, activate when needed)
- fact_service_calls[open_date] → dim_calendar[full_date]
- fact_amc[end_date] → dim_calendar[full_date]
- All facts → dim_branch, dim_product, dim_customer, dim_salesperson as appropriate.

## Core measures

```dax
Bookings Value = 
CALCULATE(
    SUM(fact_bookings[net_value_inr]),
    fact_bookings[status] IN { "Confirmed", "Delivered" }
)

Bookings MTD = 
TOTALMTD([Bookings Value], dim_calendar[full_date])

Bookings QTD = 
TOTALQTD([Bookings Value], dim_calendar[full_date])

Bookings Same Month LY = 
CALCULATE(
    [Bookings Value],
    SAMEPERIODLASTYEAR(dim_calendar[full_date])
)

Target Value = 
SUM(fact_targets[target_value_inr])

Gap to Target = 
[Bookings Value] - [Target Value]

Gap to Target % = 
DIVIDE([Gap to Target], [Target Value], 0)

Installation Backlog Value = 
CALCULATE(
    SUM(fact_installations[value_inr]),
    fact_installations[status] IN { "Scheduled", "Delayed" }
)

Open Calls Older than SLA = 
CALCULATE(
    COUNTROWS(fact_service_calls),
    fact_service_calls[status] IN { "Open", "In Progress" },
    fact_service_calls[exceeded_sla] = TRUE()
)

AMC Renewals Due This Month = 
CALCULATE(
    COUNTROWS(fact_amc),
    fact_amc[status] = "Active",
    MONTH(fact_amc[end_date]) = MONTH(TODAY()),
    YEAR(fact_amc[end_date]) = YEAR(TODAY())
)
```

## Ageing buckets (service)

```dax
Service Ageing Bucket = 
SWITCH(
    TRUE(),
    fact_service_calls[resolution_hours] <= fact_service_calls[sla_hours], "Within SLA",
    fact_service_calls[resolution_hours] <= fact_service_calls[sla_hours] * 2, "1-2x SLA",
    "Over 2x SLA"
)
```

## Reconciliation check

```dax
SQL Bookings Total (static) =  /* paste the SQL SUM result here for the period */ 0

Dashboard vs SQL Variance = [Bookings Value] - [SQL Bookings Total (static)]
```

Or maintain a small reconciliation table loaded from a SQL view that computes the same aggregates.
