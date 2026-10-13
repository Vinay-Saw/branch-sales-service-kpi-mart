# Metric Dictionary — Branch Sales, Installation & Service KPI Mart

**Dataset is simulated.** Definitions match questions branch leadership actually asks.

## Departmental flow
1. **Sales**: Leads → Inquiries → Quotations → Agreements (bookings). Only won agreements transfer to Installation.
2. **Installation**: Works at **unit** grain (BK-YYYY-NNNNNL001). Third-party vendors execute via Purchase Orders (Erection & Installation, Scaffolding, Wiring, Misc).
3. **Service**: After completion → Warranty (12/18/24 months) → AMC (Comprehensive or Non-comprehensive) introduced by Service Sales Person. Repair Orders for Non-comprehensive and units outside AMC portfolio. Service Supervisor owns the RO; Technicians execute.

## Booking / Agreement
- **Includes**: Confirmed agreements. Cancelled and On Hold remain visible for pipeline leakage.
- **Grain**: One row = one won agreement (booking_id). Units are separate (fact_units).
- **Equipment cost**: Tracked separately from total agreement value.

## Unit
- **Grain**: One row = one lift unit linked to a booking.
- Specs: product type (Passenger/Goods/Home), capacity (kg or passengers; 1 passenger = 68 kg), speed (mps), floors, stops, front/rear openings, door type, grouping (Simplex/Duplex/Triplex), material finish, license scope.
- Installation status tracked here.

## AMC
- **Types**: Comprehensive (covers all parts) vs Non-comprehensive (parts not covered).
- **Includes**: Active and historical contracts. Renewal due this month = Active where end_date is in current month.
- **Grain**: One row = one AMC contract (can have multiple over time per unit).
- Volume: 1,600+ records.

## Repair Order
- **Includes**: Work for Non-comprehensive AMC and units not under AMC (or outside warranty).
- **Grain**: One row = one repair order.
- Attributes: supervisor, technician, priority, SLA, parts/labor cost, under_warranty / under_amc flags.

## Incentives
- Available for all employee roles. Monthly amounts with basis (Target Achievement, Quality, On-time, New AMC, etc.).

## North Star per page
- Sales: Bookings vs target (or agreement value vs prior period)
- Installation: Unit backlog and third-party PO cost
- Service: Open repair orders older than SLA + AMC renewals due + warranty expiring
