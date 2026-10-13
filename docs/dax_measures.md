# DAX Measures (Power BI) — Updated for departmental model

Connect to PostgreSQL `kpi_mart`. Key relationships:

- fact_bookings[agreement_date] → dim_calendar
- fact_units[installation_complete_date] → dim_calendar (inactive)
- fact_amc[end_date] → dim_calendar
- fact_repair_orders[open_date] → dim_calendar
- All facts → dim_branch, dim_employee (role-playing where needed), dim_customer

## Sales
```dax
Bookings Value = SUM(fact_bookings[total_agreement_value_inr])
Bookings MTD = TOTALMTD([Bookings Value], dim_calendar[full_date])
Units Booked = SUM(fact_bookings[number_of_units])
Equipment Cost = SUM(fact_bookings[total_equipment_cost_inr])
```

## Installation
```dax
Units Completed = 
CALCULATE(COUNTROWS(fact_units), fact_units[installation_status] = "Completed")

Installation Backlog = 
CALCULATE(COUNTROWS(fact_units), fact_units[installation_status] IN {"Pending", "Scheduled", "In Progress"})

Third Party Cost = SUM(fact_installation_pos[amount_inr])
```

## Service
```dax
AMC Active = 
CALCULATE(COUNTROWS(fact_amc), fact_amc[status] = "Active")

AMC Renewals Due This Month = 
CALCULATE(
    COUNTROWS(fact_amc),
    fact_amc[status] = "Active",
    MONTH(fact_amc[end_date]) = MONTH(TODAY()),
    YEAR(fact_amc[end_date]) = YEAR(TODAY())
)

Open Repair Orders > SLA = 
CALCULATE(
    COUNTROWS(fact_repair_orders),
    fact_repair_orders[status] IN {"Open", "In Progress"},
    fact_repair_orders[exceeded_sla] = TRUE()
)

Repair Parts Cost = SUM(fact_repair_orders[parts_cost_inr])
```

## Incentives
```dax
Total Incentives = SUM(fact_incentives[incentive_amount_inr])
```

Use branch slicer or RLS so Surat / Vadodara / Vapi numbers stay separate.
