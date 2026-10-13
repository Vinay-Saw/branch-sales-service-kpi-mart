# ERP Boundary

Nightly export of these core tables (plus dimensions):

| Area | Table | Grain | Key columns |
|------|-------|-------|-------------|
| Sales | fact_leads | One lead | lead_date, branch, lead_generator, status |
| Sales | fact_inquiries | One inquiry | inquiry_date, salesperson, product_interest |
| Sales | fact_quotations | One quotation | quotation_date, total_value, status |
| Sales | fact_bookings | One agreement | booking_id, agreement_date, equipment_cost, number_of_units |
| Installation | fact_units | One unit | unit_id (BK-...L001), specs, installation_status, engineer |
| Installation | fact_installation_pos | One PO line | unit_id, vendor, line_item, amount |
| Service | fact_warranty | One unit | warranty_months, start/end |
| Service | fact_amc | One contract | unit_id, amc_type, start/end, annual_value |
| Service | fact_repair_orders | One RO | unit_id, supervisor, technician, SLA, costs |
| All | fact_incentives | One monthly incentive | employee, amount, basis |

**Ugly cases handled:**
- Cancelled / On Hold agreements still in pipeline
- Units with incomplete installation
- Repair orders on Non-comprehensive or out-of-AMC units
- Cross-role incentives
- Multiple AMC periods per unit
