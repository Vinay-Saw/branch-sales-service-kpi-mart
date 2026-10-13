#!/usr/bin/env python3
"""
Synthetic ERP extracts for Branch Sales, Installation & Service KPI Mart
Vertical transport company — Surat, Vadodara, Vapi branches.

Realistic departmental flow:
Sales (leads → inquiry → quotation → agreement/booking) → 
Installation (unit-level tracking + third-party POs) → 
Service (warranty → AMC + repair orders)

Dataset is simulated. No real company or personal data.
"""

import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random
import os
from collections import defaultdict

fake = Faker("en_IN")
Faker.seed(42)
np.random.seed(42)
random.seed(42)

OUT = "/workspace/artifacts/branch-kpi-mart/data"
os.makedirs(OUT, exist_ok=True)

TODAY = datetime.now().date()

# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

branches = pd.DataFrame({
    "branch_id": [1, 2, 3],
    "branch_code": ["SUR", "VAD", "VAP"],
    "branch_name": ["Surat", "Vadodara", "Vapi"],
    "state": ["Gujarat", "Gujarat", "Gujarat"],
    "region": ["South Gujarat", "Central Gujarat", "South Gujarat"],
})

# Employees with roles across departments
roles = [
    "Lead Generator", "Salesperson", "Sales Manager",
    "Installation Engineer", "Installation Manager",
    "Service Sales Person", "Service Supervisor", "Service Technician"
]
employees = []
eid = 1
for branch_id in [1, 2, 3]:
    # More sales and service staff
    role_counts = {
        "Lead Generator": 3,
        "Salesperson": 5,
        "Sales Manager": 1,
        "Installation Engineer": 4,
        "Installation Manager": 1,
        "Service Sales Person": 2,
        "Service Supervisor": 2,
        "Service Technician": 8,
    }
    for role, count in role_counts.items():
        for _ in range(count):
            employees.append({
                "employee_id": eid,
                "employee_name": fake.name(),
                "role": role,
                "branch_id": branch_id,
                "active": random.random() > 0.05,
                "hire_date": fake.date_between(start_date="-8y", end_date="-6m"),
                "incentive_eligible": True,
            })
            eid += 1
dim_employee = pd.DataFrame(employees)

# Customers
customers = []
for i in range(1, 401):
    customers.append({
        "customer_id": i,
        "customer_name": fake.company(),
        "customer_type": random.choice([
            "Residential Society", "Commercial Building", "Hospital", "Hotel",
            "Industrial", "Government", "Shopping Mall", "Educational"
        ]),
        "city": random.choice(["Surat", "Vadodara", "Vapi", "Navsari", "Bharuch", "Anand", "Valsad"]),
        "primary_branch_id": random.choice([1, 2, 3]),
    })
dim_customer = pd.DataFrame(customers)

# Third-party vendors for installation
vendors = []
for i in range(1, 16):
    vendors.append({
        "vendor_id": i,
        "vendor_name": fake.company() + " Erectors",
        "specialty": random.choice(["Erection", "Scaffolding", "Electrical", "General"]),
        "branch_coverage": random.choice([1, 2, 3, 0]),  # 0 = all
    })
dim_vendor = pd.DataFrame(vendors)

# Calendar
start = datetime(2023, 1, 1)
end = datetime(2026, 12, 31)
dates = pd.date_range(start, end, freq="D")
dim_calendar = pd.DataFrame({
    "date_key": dates.strftime("%Y%m%d").astype(int),
    "full_date": dates,
    "year": dates.year,
    "quarter": dates.quarter,
    "month": dates.month,
    "month_name": dates.strftime("%B"),
    "year_month": dates.strftime("%Y-%m"),
    "day_of_week": dates.dayofweek + 1,
    "is_weekend": dates.dayofweek >= 5,
    "fiscal_year": dates.year + (dates.month >= 4).astype(int),
    "fiscal_quarter": ((dates.month - 4) % 12 // 3) + 1,
})

# ---------------------------------------------------------------------------
# Helper to pick employee by role and branch
# ---------------------------------------------------------------------------
def pick_emp(role, branch_id):
    pool = dim_employee[(dim_employee.role == role) & (dim_employee.branch_id == branch_id) & (dim_employee.active)]
    if pool.empty:
        pool = dim_employee[(dim_employee.role == role) & (dim_employee.active)]
    return pool.sample(1).iloc[0].employee_id if not pool.empty else 1

# ---------------------------------------------------------------------------
# Sales flow: Leads → Inquiries → Quotations → Agreements (Bookings)
# ---------------------------------------------------------------------------
leads = []
inquiries = []
quotations = []
bookings = []  # won agreements
units = []     # unit-level detail

lead_id = 1
inq_id = 1
quo_id = 1
booking_seq = 1
unit_seq_per_booking = defaultdict(int)

# Generate ~4500 leads over 3 years for more volume
for _ in range(4500):
    lead_date = fake.date_between(start_date="-3y", end_date="today")
    branch_id = random.choices([1, 2, 3], weights=[0.42, 0.35, 0.23])[0]
    lg_id = pick_emp("Lead Generator", branch_id)
    # Some leads have existing customer, some are new
    if random.random() < 0.4:
        cust = dim_customer.sample(1).iloc[0]
        cust_id = cust.customer_id
        prospect_name = None
    else:
        cust_id = None
        prospect_name = fake.company()
    status = random.choices(["New", "Qualified", "Lost", "Converted"], weights=[0.15, 0.25, 0.35, 0.25])[0]
    leads.append({
        "lead_id": lead_id,
        "lead_date": lead_date,
        "branch_id": branch_id,
        "lead_generator_id": lg_id,
        "customer_id": cust_id,
        "prospect_name": prospect_name,
        "source": random.choice(["Website", "Referral", "Cold Call", "Exhibition", "Existing Customer", "Architect"]),
        "status": status,
    })
    current_lead = lead_id
    lead_id += 1

    # Only some leads become inquiries
    if status in ["Qualified", "Converted"] or random.random() < 0.3:
        inq_date = lead_date + timedelta(days=random.randint(1, 20))
        if inq_date > TODAY:
            continue
        sp_id = pick_emp("Salesperson", branch_id)
        if cust_id is None:
            # Convert prospect to customer for inquiry
            new_cust_id = len(dim_customer) + 1
            dim_customer = pd.concat([dim_customer, pd.DataFrame([{
                "customer_id": new_cust_id,
                "customer_name": prospect_name or fake.company(),
                "customer_type": random.choice(["Residential Society", "Commercial Building", "Hospital"]),
                "city": random.choice(["Surat", "Vadodara", "Vapi"]),
                "primary_branch_id": branch_id,
            }])], ignore_index=True)
            cust_id = new_cust_id
        inquiries.append({
            "inquiry_id": inq_id,
            "lead_id": current_lead,
            "inquiry_date": inq_date,
            "customer_id": cust_id,
            "branch_id": branch_id,
            "salesperson_id": sp_id,
            "product_interest": random.choice(["Passenger Lift", "Goods Lift", "Home Lift", "Hospital Lift"]),
            "status": random.choice(["Open", "Quoted", "Won", "Lost"]),
        })
        current_inq = inq_id
        inq_id += 1

        # Quotations
        if random.random() < 0.75:
            quo_date = inq_date + timedelta(days=random.randint(2, 15))
            if quo_date > TODAY:
                continue
            total_value = random.randint(350000, 2500000)
            quo_status = random.choices(["Sent", "Revised", "Accepted", "Rejected"], weights=[0.2, 0.15, 0.45, 0.2])[0]
            quotations.append({
                "quotation_id": quo_id,
                "inquiry_id": current_inq,
                "quotation_date": quo_date,
                "salesperson_id": sp_id,
                "branch_id": branch_id,
                "total_value_inr": total_value,
                "status": quo_status,
            })
            current_quo = quo_id
            quo_id += 1

            # Won agreements → bookings
            if quo_status == "Accepted" and random.random() < 0.92:
                agr_date = quo_date + timedelta(days=random.randint(3, 25))
                if agr_date > TODAY:
                    continue
                sm_id = pick_emp("Sales Manager", branch_id)
                n_units = random.choices([1, 2, 3, 4, 5], weights=[0.45, 0.30, 0.15, 0.07, 0.03])[0]
                booking_id = f"BK-{agr_date.year}-{booking_seq:05d}"
                total_equip = int(total_value * random.uniform(0.72, 0.88))
                bookings.append({
                    "booking_id": booking_id,
                    "agreement_date": agr_date,
                    "quotation_id": current_quo,
                    "inquiry_id": current_inq,
                    "lead_id": current_lead,
                    "customer_id": cust_id,
                    "branch_id": branch_id,
                    "salesperson_id": sp_id,
                    "sales_manager_id": sm_id,
                    "number_of_units": n_units,
                    "total_equipment_cost_inr": total_equip,
                    "total_agreement_value_inr": total_value,
                    "status": random.choices(["Confirmed", "Cancelled", "On Hold"], weights=[0.88, 0.07, 0.05])[0],
                })
                booking_seq += 1

                # Create units for this booking
                for u in range(1, n_units + 1):
                    unit_id = f"{booking_id}L{u:03d}"
                    ptype = random.choices(["Passenger", "Goods", "Home"], weights=[0.65, 0.2, 0.15])[0]
                    if ptype == "Passenger":
                        cap_pass = random.choice([6, 8, 10, 13, 15])
                        cap_kg = cap_pass * 68
                    elif ptype == "Goods":
                        cap_kg = random.choice([500, 1000, 1500, 2000])
                        cap_pass = None
                    else:
                        cap_pass = random.choice([3, 4, 5])
                        cap_kg = cap_pass * 68
                    speed = random.choice([0.5, 0.63, 1.0, 1.5, 1.75]) if ptype != "Home" else 0.4
                    floors = random.choice(["G+5", "G+8", "B1+G+7", "B2+B1+G+12", "G+15", "B1+G+10"])
                    stops = int(floors.split("+")[-1]) + floors.count("B") + 1
                    front_open = random.randint(stops - 2, stops)
                    rear_open = random.choice([0, 0, 1, 2]) if random.random() < 0.3 else 0
                    equip_cost = int(total_equip / n_units * random.uniform(0.9, 1.1))
                    units.append({
                        "unit_id": unit_id,
                        "booking_id": booking_id,
                        "unit_number": u,
                        "customer_id": cust_id,
                        "branch_id": branch_id,
                        "product_type": ptype,
                        "capacity_kg": cap_kg,
                        "capacity_passengers": cap_pass,
                        "speed_mps": speed,
                        "floors_description": floors,
                        "no_of_stops": stops,
                        "front_openings": front_open,
                        "rear_openings": rear_open,
                        "door_opening_type": random.choice(["Center", "Telescopic"]),
                        "grouping": random.choice(["Simplex", "Duplex", "Triplex"]) if n_units > 1 else "Simplex",
                        "door_type": random.choice(["No Vision", "Small Vision", "Big Vision - Glass Door"]),
                        "material_finish": random.choice(["SS", "SS 304", "Honeycomb", "Rose Gold", "Hairline SS"]),
                        "license_scope": random.choice(["Company Scope", "Customer Scope"]),
                        "equipment_cost_inr": equip_cost,
                        "installation_status": "Pending",  # will update later
                    })

fact_leads = pd.DataFrame(leads)
fact_inquiries = pd.DataFrame(inquiries)
fact_quotations = pd.DataFrame(quotations)
fact_bookings = pd.DataFrame(bookings)
fact_units = pd.DataFrame(units)

print(f"Leads: {len(fact_leads)}, Inquiries: {len(fact_inquiries)}, Quotations: {len(fact_quotations)}")
print(f"Bookings: {len(fact_bookings)}, Units: {len(fact_units)}")

# ---------------------------------------------------------------------------
# Installation: progress on units + third-party POs
# ---------------------------------------------------------------------------
installation_pos = []
po_id = 1
line_items = ["Erection & Installation Charges", "Scaffolding Charges", "Wiring Charges", "Misc Project Cost"]

for idx, unit in fact_units.iterrows():
    if unit.booking_id not in fact_bookings[fact_bookings.status == "Confirmed"].booking_id.values:
        continue
    booking = fact_bookings[fact_bookings.booking_id == unit.booking_id].iloc[0]
    if booking.status != "Confirmed":
        continue
    # Installation starts 25-70 days after agreement
    start_offset = random.randint(25, 70)
    install_start = booking.agreement_date + timedelta(days=start_offset)
    if install_start > TODAY:
        fact_units.at[idx, "installation_status"] = "Scheduled"
        continue
    # Completion
    duration = random.randint(20, 60)
    complete_date = install_start + timedelta(days=duration)
    if complete_date > TODAY:
        status = "In Progress"
        actual_complete = None
    else:
        status = random.choices(["Completed", "Delayed"], weights=[0.82, 0.18])[0]
        actual_complete = complete_date if status == "Completed" else complete_date + timedelta(days=random.randint(5, 30))
    fact_units.at[idx, "installation_status"] = status
    fact_units.at[idx, "installation_start_date"] = install_start
    fact_units.at[idx, "installation_complete_date"] = actual_complete
    fact_units.at[idx, "installation_engineer_id"] = pick_emp("Installation Engineer", unit.branch_id)

    # Third-party POs for this unit
    for item in line_items:
        if random.random() < 0.85:  # not every unit has every line
            amount = random.randint(15000, 120000) if "Misc" not in item else random.randint(5000, 40000)
            vendor = dim_vendor.sample(1).iloc[0]
            po_date = install_start - timedelta(days=random.randint(5, 20))
            installation_pos.append({
                "po_id": po_id,
                "unit_id": unit.unit_id,
                "booking_id": unit.booking_id,
                "branch_id": unit.branch_id,
                "vendor_id": vendor.vendor_id,
                "line_item": item,
                "amount_inr": amount,
                "po_date": po_date,
                "status": "Closed" if status == "Completed" else "Open",
            })
            po_id += 1

fact_installation_pos = pd.DataFrame(installation_pos)
print(f"Installation POs: {len(fact_installation_pos)}")

# ---------------------------------------------------------------------------
# Warranty + AMC + Repair Orders
# ---------------------------------------------------------------------------
warranty = []
amc_list = []
repair_orders = []
amc_id = 1
ro_id = 1

completed_units = fact_units[fact_units.installation_status == "Completed"].copy()
print(f"Completed units: {len(completed_units)}")

for _, unit in completed_units.iterrows():
    complete = unit.installation_complete_date
    if pd.isna(complete):
        continue
    w_months = random.choice([12, 18, 24])
    w_end = complete + timedelta(days=w_months * 30)
    warranty.append({
        "unit_id": unit.unit_id,
        "booking_id": unit.booking_id,
        "customer_id": unit.customer_id,
        "branch_id": unit.branch_id,
        "warranty_start_date": complete,
        "warranty_months": w_months,
        "warranty_end_date": w_end,
        "status": "Active" if w_end >= TODAY else "Expired",
    })

    # Generate AMC for most completed units (target 1500+)
    # Include some that start before warranty ends (early conversion)
    if random.random() < 0.92:
        # Prefer start after warranty, but allow earlier for volume
        if w_end < TODAY:
            amc_start = w_end + timedelta(days=random.randint(1, 60))
        else:
            # Early AMC or projected
            amc_start = complete + timedelta(days=random.randint(60, 200))
        if amc_start > TODAY:
            # Still create some future-starting AMC
            if random.random() > 0.4:
                pass
            else:
                amc_start = TODAY - timedelta(days=random.randint(30, 180))
        if amc_start > TODAY:
            continue
        amc_type = random.choices(["Comprehensive", "Non-comprehensive"], weights=[0.48, 0.52])[0]
        term_years = random.choice([1, 1, 1, 2, 3])
        amc_end = amc_start + timedelta(days=365 * term_years - 8)
        ssp_id = pick_emp("Service Sales Person", unit.branch_id)
        annual_val = random.randint(32000, 155000)
        # Some renewed
        if amc_end < TODAY and random.random() < 0.65:
            amc_start = amc_end + timedelta(days=random.randint(1, 40))
            amc_end = amc_start + timedelta(days=365 * random.choice([1, 2]) - 5)
        amc_list.append({
            "amc_id": amc_id,
            "unit_id": unit.unit_id,
            "booking_id": unit.booking_id,
            "customer_id": unit.customer_id,
            "branch_id": unit.branch_id,
            "service_salesperson_id": ssp_id,
            "amc_type": amc_type,
            "start_date": amc_start,
            "end_date": amc_end,
            "annual_value_inr": annual_val,
            "status": "Active" if amc_end >= TODAY else "Expired",
            "renewal_due_month": amc_end.strftime("%Y-%m") if amc_end >= TODAY else None,
        })
        amc_id += 1

    # Repair orders (more for non-comprehensive and out-of-portfolio)
    n_repairs = random.choices([0, 1, 2, 3, 4, 5], weights=[0.2, 0.3, 0.25, 0.15, 0.07, 0.03])[0]
    for _ in range(n_repairs):
        open_dt = complete + timedelta(days=random.randint(30, 800))
        if open_dt > TODAY:
            continue
        is_under_warranty = open_dt <= w_end
        # Check if under AMC
        under_amc = False
        amc_type_for_ro = None
        for a in amc_list:
            if a["unit_id"] == unit.unit_id and a["start_date"] <= open_dt <= a["end_date"]:
                under_amc = True
                amc_type_for_ro = a["amc_type"]
                break
        # Repair more common if not comprehensive or not under AMC
        if under_amc and amc_type_for_ro == "Comprehensive" and random.random() < 0.6:
            continue
        sup_id = pick_emp("Service Supervisor", unit.branch_id)
        tech_id = pick_emp("Service Technician", unit.branch_id)
        priority = random.choices(["P1-Critical", "P2-High", "P3-Normal"], weights=[0.15, 0.35, 0.5])[0]
        sla_h = {"P1-Critical": 4, "P2-High": 8, "P3-Normal": 24}[priority]
        if open_dt > TODAY - timedelta(days=10):
            status = random.choice(["Open", "In Progress"])
            close_dt = None
            res_h = None
            exceeded = (TODAY - open_dt).days * 24 > sla_h
        else:
            status = random.choices(["Closed", "Open"], weights=[0.9, 0.1])[0]
            if status == "Closed":
                res_h = max(1, int(np.random.lognormal(np.log(sla_h * 0.6), 0.45)))
                if random.random() < 0.15:
                    res_h = int(sla_h * random.uniform(1.2, 2.8))
                close_dt = open_dt + timedelta(hours=res_h)
                exceeded = res_h > sla_h
            else:
                close_dt = None
                res_h = None
                exceeded = (TODAY - open_dt).days * 24 > sla_h
        parts = random.randint(0, 45000) if not (under_amc and amc_type_for_ro == "Comprehensive") else random.randint(0, 8000)
        labor = random.randint(2000, 15000)
        repair_orders.append({
            "repair_order_id": ro_id,
            "unit_id": unit.unit_id,
            "booking_id": unit.booking_id,
            "customer_id": unit.customer_id,
            "branch_id": unit.branch_id,
            "open_date": open_dt,
            "close_date": close_dt,
            "service_supervisor_id": sup_id,
            "technician_id": tech_id,
            "priority": priority,
            "sla_hours": sla_h,
            "resolution_hours": res_h,
            "status": status,
            "is_under_warranty": is_under_warranty,
            "is_under_amc": under_amc,
            "amc_type": amc_type_for_ro,
            "parts_cost_inr": parts,
            "labor_cost_inr": labor,
            "exceeded_sla": exceeded,
            "description": random.choice([
                "Door sensor fault", "Controller error", "Motor overheating",
                "Cable wear", "Button panel issue", "Safety gear check", "Oil leak", "Vibration"
            ]),
        })
        ro_id += 1

# Ensure 1500+ AMC records by adding additional historical contracts
while len(amc_list) < 1600:
    unit = completed_units.sample(1).iloc[0]
    complete = unit.installation_complete_date
    if pd.isna(complete):
        continue
    amc_start = complete + timedelta(days=random.randint(90, 400))
    if amc_start > TODAY:
        amc_start = TODAY - timedelta(days=random.randint(60, 500))
    amc_type = random.choices(["Comprehensive", "Non-comprehensive"], weights=[0.5, 0.5])[0]
    term_years = random.choice([1, 2])
    amc_end = amc_start + timedelta(days=365 * term_years - 10)
    ssp_id = pick_emp("Service Sales Person", unit.branch_id)
    annual_val = random.randint(30000, 140000)
    amc_list.append({
        "amc_id": amc_id,
        "unit_id": unit.unit_id,
        "booking_id": unit.booking_id,
        "customer_id": unit.customer_id,
        "branch_id": unit.branch_id,
        "service_salesperson_id": ssp_id,
        "amc_type": amc_type,
        "start_date": amc_start,
        "end_date": amc_end,
        "annual_value_inr": annual_val,
        "status": "Active" if amc_end >= TODAY else "Expired",
        "renewal_due_month": amc_end.strftime("%Y-%m") if amc_end >= TODAY else None,
    })
    amc_id += 1

fact_warranty = pd.DataFrame(warranty)
fact_amc = pd.DataFrame(amc_list)
fact_repair_orders = pd.DataFrame(repair_orders)

print(f"Warranty: {len(fact_warranty)}, AMC: {len(fact_amc)}, Repair Orders: {len(fact_repair_orders)}")

# ---------------------------------------------------------------------------
# Incentives (sample periods)
# ---------------------------------------------------------------------------
incentives = []
inc_id = 1
for year in [2024, 2025, 2026]:
    for month in range(1, 13):
        if datetime(year, month, 1).date() > TODAY:
            break
        for _, emp in dim_employee[dim_employee.active].iterrows():
            if random.random() < 0.55:  # not everyone every month
                base = {"Salesperson": 8000, "Sales Manager": 12000, "Lead Generator": 3000,
                        "Installation Engineer": 5000, "Service Technician": 2500,
                        "Service Supervisor": 4000, "Service Sales Person": 6000,
                        "Installation Manager": 7000}.get(emp.role, 2000)
                amount = int(base * random.uniform(0.4, 1.8))
                incentives.append({
                    "incentive_id": inc_id,
                    "employee_id": emp.employee_id,
                    "branch_id": emp.branch_id,
                    "year": year,
                    "month": month,
                    "role": emp.role,
                    "incentive_amount_inr": amount,
                    "basis": random.choice(["Target Achievement", "Quality", "On-time", "New AMC", "Collection"]),
                })
                inc_id += 1
fact_incentives = pd.DataFrame(incentives)
print(f"Incentives: {len(fact_incentives)}")

# ---------------------------------------------------------------------------
# Save all
# ---------------------------------------------------------------------------
branches.to_csv(f"{OUT}/dim_branch.csv", index=False)
dim_employee.to_csv(f"{OUT}/dim_employee.csv", index=False)
dim_customer.to_csv(f"{OUT}/dim_customer.csv", index=False)
dim_vendor.to_csv(f"{OUT}/dim_vendor.csv", index=False)
dim_calendar.to_csv(f"{OUT}/dim_calendar.csv", index=False)

fact_leads.to_csv(f"{OUT}/fact_leads.csv", index=False)
fact_inquiries.to_csv(f"{OUT}/fact_inquiries.csv", index=False)
fact_quotations.to_csv(f"{OUT}/fact_quotations.csv", index=False)
fact_bookings.to_csv(f"{OUT}/fact_bookings.csv", index=False)
fact_units.to_csv(f"{OUT}/fact_units.csv", index=False)
fact_installation_pos.to_csv(f"{OUT}/fact_installation_pos.csv", index=False)
fact_warranty.to_csv(f"{OUT}/fact_warranty.csv", index=False)
fact_amc.to_csv(f"{OUT}/fact_amc.csv", index=False)
fact_repair_orders.to_csv(f"{OUT}/fact_repair_orders.csv", index=False)
fact_incentives.to_csv(f"{OUT}/fact_incentives.csv", index=False)

print("\n=== Final counts ===")
for f in sorted(os.listdir(OUT)):
    if f.endswith(".csv"):
        df = pd.read_csv(f"{OUT}/{f}")
        print(f"  {f}: {len(df):,} rows")
print("Done.")
