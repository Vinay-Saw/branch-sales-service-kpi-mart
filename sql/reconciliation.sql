-- Reconciliation queries

-- Bookings value
SELECT SUM(total_agreement_value_inr) AS bookings_value
FROM kpi_mart.fact_bookings
WHERE status = 'Confirmed';

-- Units by installation status
SELECT installation_status, COUNT(*) 
FROM kpi_mart.fact_units 
GROUP BY 1;

-- AMC active and due this month
SELECT 
  COUNT(*) FILTER (WHERE status = 'Active') AS active_amc,
  COUNT(*) FILTER (WHERE status = 'Active' AND TO_CHAR(end_date, 'YYYY-MM') = TO_CHAR(CURRENT_DATE, 'YYYY-MM')) AS due_this_month
FROM kpi_mart.fact_amc;

-- Open repair orders exceeding SLA
SELECT COUNT(*) AS open_over_sla
FROM kpi_mart.fact_repair_orders
WHERE status IN ('Open', 'In Progress') AND exceeded_sla = true;

-- Third-party installation cost
SELECT SUM(amount_inr) AS total_po_cost
FROM kpi_mart.fact_installation_pos;
