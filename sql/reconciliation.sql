-- Reconciliation queries (run in PostgreSQL)
-- Dashboard total must equal these numbers for the same filters.

-- Bookings value (Confirmed + Delivered) — all time
SELECT SUM(net_value_inr) AS bookings_value
FROM kpi_mart.fact_bookings
WHERE status IN ('Confirmed', 'Delivered');

-- Bookings value by branch
SELECT b.branch_name, SUM(f.net_value_inr) AS bookings_value
FROM kpi_mart.fact_bookings f
JOIN kpi_mart.dim_branch b ON f.branch_id = b.branch_id
WHERE f.status IN ('Confirmed', 'Delivered')
GROUP BY b.branch_name
ORDER BY 1;

-- Open service calls older than SLA
SELECT COUNT(*) AS open_over_sla
FROM kpi_mart.fact_service_calls
WHERE status IN ('Open', 'In Progress')
  AND exceeded_sla = true;

-- Installation backlog value
SELECT SUM(value_inr) AS backlog_value
FROM kpi_mart.fact_installations
WHERE status IN ('Scheduled', 'Delayed');

-- AMC renewals due this month (example for October 2026 — adjust)
SELECT COUNT(*) AS amc_due
FROM kpi_mart.fact_amc
WHERE status = 'Active'
  AND EXTRACT(MONTH FROM end_date) = EXTRACT(MONTH FROM CURRENT_DATE)
  AND EXTRACT(YEAR FROM end_date) = EXTRACT(YEAR FROM CURRENT_DATE);
