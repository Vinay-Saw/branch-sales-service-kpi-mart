# Requirement Note (Stakeholder Language)

**Question leadership asks:**  
“Which branch is off target, and is it a sales problem or a delivery problem?”

**What the model answers without a new export:**
1. Bookings vs target (MTD, QTD, same month last year) by branch and product type.
2. Installation backlog (scheduled or delayed jobs) by branch — shows if confirmed bookings are not being installed.
3. Open service calls older than SLA by branch — operational pressure that can affect customer satisfaction and renewal.
4. AMC renewals due this month by branch — revenue at risk on the service side.

**Row-level security / branch view:**  
Three branches do not share one number. Either implement RLS so a branch manager sees only their branch, or keep a single model with a prominent branch slicer and document that the unfiltered total is the company view.

**Reconciliation:**  
Dashboard total bookings (Confirmed + Delivered) equals the SQL total from fact_bookings. A short reconciliation page or measure pair proves the extract and the model stay in sync.
