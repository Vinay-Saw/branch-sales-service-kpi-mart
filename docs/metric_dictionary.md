# Metric Dictionary — Branch Sales & Service KPI Mart

**Dataset is simulated.** Definitions match questions branch leadership actually asks.

## Booking
- **Includes**: Confirmed and Delivered booking lines (net value). On Hold is tracked but excluded from “booked” totals.
- **Excludes**: Cancelled orders (still appear in the pipeline table with status = Cancelled so leadership can see leakage).
- **Grain**: One row = one booking line (product + quantity on one booking). A multi-product order produces multiple rows.
- **Measure**: Bookings Value = SUM(net_value_inr) WHERE status IN ('Confirmed', 'Delivered').

## Installation Backlog
- **Includes**: Installation jobs with status IN ('Scheduled', 'Delayed') and scheduled_date <= today or within next 60 days.
- **Excludes**: Completed and Cancelled.
- **Grain**: One row = one installation job linked to a booking line.

## Open Service Calls Older than SLA
- **Includes**: status IN ('Open', 'In Progress') AND (current_date - open_date) * 24 > sla_hours.
- **Cross-branch**: A call opened in one branch and closed in another is attributed to the open_branch for backlog and to close_branch for resolution metrics. Both are stored.
- **Grain**: One row = one service call.

## AMC Renewal Due This Month
- **Includes**: Active contracts where end_date falls in the current calendar month.
- **Excludes**: Already renewed (new contract row created) or expired without renewal.
- **Grain**: One row = one AMC contract.

## Target Variance
- **Definition**: Bookings Value (MTD / QTD / YTD) − Target Value for the same period.
- **Mid-quarter revision**: fact_targets.revised_mid_period = true. The measure uses the latest target value; revision_date is available for audit.
- **Not a calculated column**: Implemented as a DAX measure so it recalculates with any filter (branch, product type, time).

## Ageing Buckets (Service)
- 0–SLA: within SLA
- SLA–2×SLA: mildly overdue
- >2×SLA: severely overdue

## North Star per Page
- Sales page: Bookings vs Target (gap)
- Delivery page: Installation backlog value and count
- Service page: Open calls older than SLA + AMC renewals due
