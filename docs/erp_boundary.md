# ERP Boundary

Nightly export (or CDC) of these four core tables plus supporting dimensions:

| Table | Grain | Key columns |
|-------|-------|-------------|
| Bookings | One booking line | booking_line_id, booking_date, branch_id, salesperson_id, customer_id, product_id, quantity, net_value_inr, status |
| Installations | One installation job | installation_id, booking_line_id, scheduled_date, actual_completion_date, status, branch_id |
| Service Calls | One service call | service_call_id, open_date, close_date, open_branch_id, close_branch_id, priority, sla_hours, status |
| AMC Contracts | One contract | amc_id, customer_id, branch_id, start_date, end_date, annual_value_inr, status |

Dimensions (branch, product, salesperson, customer, calendar) are refreshed less frequently or maintained as reference data.

**Ugly cases handled:**
- Cancelled order still appears in the bookings fact with status = Cancelled (visible in pipeline, excluded from booked totals).
- Target can change mid-quarter (revised_mid_period flag + revision_date).
- Service call opened in one branch and closed in another (both branch IDs stored).
